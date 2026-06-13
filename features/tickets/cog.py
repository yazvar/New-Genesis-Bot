from __future__ import annotations

import logging
import re

import discord
from discord.ext import commands

from bot.panels import PanelBinding, sync_panel
from config.settings import Settings
from features.tickets.embeds import (
    DEFAULT_PANEL_CATEGORY,
    build_panel_embed,
    build_ticket_embed,
    get_category,
)
from features.tickets.state import TicketStore
from features.tickets.transcript import deliver_ticket_logs
from features.tickets.views import (
    CloseConfirmView,
    TicketMessageView,
    TicketModal,
    TicketPanelView,
)
from utils.interactions import ephemeral_reply

logger = logging.getLogger(__name__)

PANEL_WEBHOOK_NAME = "New Genesis • Тикеты"


class TicketsCog(commands.Cog):
    """Центр поддержки: панель → модал → приватный канал → принять / закрыть."""

    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self.store = TicketStore()
        self.panel_view = TicketPanelView(self)
        self._selected_categories: dict[int, str] = {}

    async def cog_load(self) -> None:
        self.panel_view = TicketPanelView(self)

    def set_selected_category(self, user_id: int, category: str | None) -> None:
        if category is None:
            self._selected_categories.pop(user_id, None)
        else:
            self._selected_categories[user_id] = category

    def get_selected_category(self, user_id: int) -> str:
        return self._selected_categories.get(user_id, DEFAULT_PANEL_CATEGORY)

    def _panel_binding(self) -> PanelBinding | None:
        panel = self.store.panel
        if panel is None:
            return None
        return PanelBinding(panel.channel_id, panel.message_id, panel.webhook_id)

    async def ensure_panel(self) -> None:
        self.panel_view = TicketPanelView(self)
        embed = build_panel_embed(self.settings)
        binding = await sync_panel(
            self.bot,
            channel_id=self.settings.ticket_panel_channel_id,
            webhook_url=None,
            webhook_name=PANEL_WEBHOOK_NAME,
            panel=self._panel_binding(),
            set_panel=self.store.set_panel,
            embed=embed,
            view=self.panel_view,
        )
        if binding is None and self.settings.ticket_panel_channel_id is None:
            logger.warning(
                "TICKET_PANEL_CHANNEL_ID не задан — панель тикетов не опубликована"
            )

    def _register_ticket_view(
        self,
        channel_id: int,
        ticket=None,
    ) -> TicketMessageView:
        return TicketMessageView(self, channel_id, ticket)

    def _build_ticket_embed(self, ticket) -> discord.Embed:
        return build_ticket_embed(
            self.settings,
            ticket_id=ticket.ticket_id,
            category=ticket.category,
            creator_id=ticket.creator_id,
            creator_name=ticket.creator_name,
            staff_id=ticket.staff_id,
            staff_name=ticket.staff_name,
            closed_at=ticket.closed_at,
            created_at=ticket.created_at,
        )

    @staticmethod
    def _member_has_any_role(
        member: discord.Member,
        role_ids: tuple[int, ...],
    ) -> bool:
        if not role_ids:
            return False
        member_role_ids = {role.id for role in member.roles}
        return any(role_id in member_role_ids for role_id in role_ids)

    def _is_staff(self, member: discord.Member) -> bool:
        return self._member_has_any_role(member, self.settings.ticket_staff_role_ids)

    def _can_manage_ticket(self, member: discord.Member, ticket) -> bool:
        """Принимать/закрывать тикеты может только поддержка."""
        return self._is_staff(member)

    async def _fetch_ticket_message(self, ticket):
        channel = self.bot.get_channel(ticket.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                channel = await self.bot.fetch_channel(ticket.channel_id)
            except discord.HTTPException:
                return None

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return None

        try:
            return await channel.fetch_message(ticket.message_id)
        except discord.NotFound:
            return None
        except discord.HTTPException as exc:
            logger.warning(
                "Ошибка загрузки сообщения тикета %s: %s",
                ticket.ticket_id,
                exc,
            )
            return None

    async def _get_category_channel(
        self,
        guild: discord.Guild,
        category_id: int | None = None,
    ) -> discord.CategoryChannel | None:
        resolved_id = category_id if category_id is not None else self.settings.ticket_category_id
        if resolved_id is None:
            return None

        channel = guild.get_channel(resolved_id)
        if isinstance(channel, discord.CategoryChannel):
            return channel

        try:
            fetched = await guild.fetch_channel(resolved_id)
        except discord.HTTPException:
            return None

        return fetched if isinstance(fetched, discord.CategoryChannel) else None

    def _make_channel_name(self, ticket_id: int, category: str, member: discord.Member) -> str:
        cat = get_category(category)
        slug = re.sub(r"[^a-z0-9]+", "-", member.name.lower()).strip("-")[:20]
        if not slug:
            slug = str(member.id)[-6:]
        label_slug = re.sub(r"[^a-z0-9]+", "-", cat["label"].lower()).strip("-")[:20]
        parts = ["ticket", str(ticket_id)]
        if label_slug:
            parts.append(label_slug)
        parts.append(slug)
        return "-".join(parts)[:100]

    async def restore_ticket_messages(self) -> int:
        restored = 0

        for ticket in list(self.store.open_tickets):
            message = await self._fetch_ticket_message(ticket)
            if message is None:
                logger.warning(
                    "Сообщение тикета #%s не найдено — удаляем из памяти бота",
                    ticket.ticket_id,
                )
                self.store.remove_ticket(ticket.channel_id)
                continue

            embed = self._build_ticket_embed(ticket)

            try:
                await message.edit(embed=embed)
                restored += 1
            except discord.HTTPException as exc:
                logger.warning(
                    "Не удалось восстановить тикет #%s: %s",
                    ticket.ticket_id,
                    exc,
                )

        return restored

    async def show_ticket_modal(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return

        if interaction.guild is None:
            await ephemeral_reply(
                interaction,
                "Тикеты можно создавать только на сервере.",
            )
            return

        category = self.get_selected_category(interaction.user.id)
        await interaction.response.send_modal(TicketModal(self, category))

    async def create_ticket_from_modal(
        self,
        interaction: discord.Interaction,
        *,
        category: str,
        form_description: str,
        form_player: str | None = None,
        form_extra: str | None = None,
        discord_category_id: int | None = None,
    ) -> None:
        if interaction.response.is_done():
            return

        if interaction.guild is None:
            await ephemeral_reply(
                interaction,
                "Тикеты можно создавать только на сервере.",
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await ephemeral_reply(
                interaction,
                "Не удалось определить участника сервера.",
            )
            return

        member = interaction.user
        open_count = self.store.count_open_by_user(member.id)
        if open_count >= self.settings.ticket_max_per_user:
            await ephemeral_reply(
                interaction,
                f"У вас уже **{open_count}** активных тикетов. "
                f"Лимит — **{self.settings.ticket_max_per_user}**. "
                "Закройте один из них, чтобы создать новый.",
            )
            return

        category_channel = await self._get_category_channel(
            interaction.guild,
            discord_category_id,
        )
        if category_channel is None:
            await ephemeral_reply(
                interaction,
                "Категория для тикетов не настроена. Сообщите администратору.",
            )
            logger.warning(
                "Категория тикетов не задана или недоступна (id=%s)",
                discord_category_id or self.settings.ticket_category_id,
            )
            return

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }

        # Тикет видят автор, бот и роли поддержки
        access_role_ids = self.settings.ticket_staff_role_ids

        for access_role_id in access_role_ids:
            access_role = interaction.guild.get_role(access_role_id)
            if access_role is not None:
                overwrites[access_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        next_id = self.store.next_ticket_id
        channel_name = self._make_channel_name(next_id, category, member)

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category_channel,
                overwrites=overwrites,
                reason=f"Тикет от {member.display_name}",
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                "Не удалось создать канал тикета. Попробуйте позже.",
                ephemeral=True,
            )
            logger.warning("Ошибка создания канала тикета: %s", exc)
            return

        embed = build_ticket_embed(
            self.settings,
            ticket_id=next_id,
            category=category,
            creator_id=member.id,
            creator_name=member.display_name,
            form_description=form_description,
            form_player=form_player,
            form_extra=form_extra,
        )

        try:
            message = await ticket_channel.send(
                content=member.mention,
                embed=embed,
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                "Канал создан, но не удалось отправить приветственное сообщение.",
                ephemeral=True,
            )
            logger.warning("Ошибка отправки сообщения тикета: %s", exc)
            return

        view = self._register_ticket_view(ticket_channel.id)

        try:
            await message.edit(view=view)
        except discord.HTTPException as exc:
            logger.warning(
                "Не удалось добавить кнопки к тикету #%s: %s",
                next_id,
                exc,
            )

        ticket = self.store.add_ticket(
            channel_id=ticket_channel.id,
            message_id=message.id,
            category=category,
            creator_id=member.id,
            creator_name=member.display_name,
        )

        self._selected_categories.pop(member.id, None)

        await interaction.followup.send(
            f"✅ Тикет **#{ticket.ticket_id}** создан: {ticket_channel.mention}",
            ephemeral=True,
        )

    async def accept_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
    ) -> None:
        if interaction.response.is_done():
            return

        ticket = self.store.get_ticket(channel_id)

        if ticket is None or not ticket.is_open:
            await ephemeral_reply(interaction, "Тикет не найден или уже закрыт.")
            return

        if not isinstance(interaction.user, discord.Member):
            await ephemeral_reply(
                interaction,
                "Не удалось определить участника сервера.",
            )
            return

        if not self._can_manage_ticket(interaction.user, ticket):
            await ephemeral_reply(
                interaction,
                "Принять тикет может только участник с **ролью поддержки**.",
            )
            return

        if ticket.is_accepted:
            staff = ticket.staff_name or "другой сотрудник"
            await ephemeral_reply(
                interaction,
                f"Этот тикет уже принял **{staff}**.",
            )
            return

        member = interaction.user
        display_name = member.display_name

        updated = self.store.accept_ticket(channel_id, member.id, display_name)
        if updated is None:
            await ephemeral_reply(
                interaction,
                "Не удалось принять тикет. Попробуйте ещё раз.",
            )
            return

        embed = self._build_ticket_embed(updated)
        view = self._register_ticket_view(channel_id, updated)

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.HTTPException as exc:
            await ephemeral_reply(
                interaction,
                "Тикет принят, но не удалось обновить сообщение.",
            )
            logger.warning("Ошибка обновления тикета #%s: %s", ticket.ticket_id, exc)
            return

        await interaction.followup.send(
            f"✅ Вы приняли тикет **#{ticket.ticket_id}**.",
            ephemeral=True,
        )

    async def request_close_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
    ) -> None:
        if interaction.response.is_done():
            return

        ticket = self.store.get_ticket(channel_id)

        if ticket is None or not ticket.is_open:
            await ephemeral_reply(interaction, "Тикет не найден или уже закрыт.")
            return

        if not isinstance(interaction.user, discord.Member):
            await ephemeral_reply(
                interaction,
                "Не удалось определить участника сервера.",
            )
            return

        if not self._can_manage_ticket(interaction.user, ticket):
            await ephemeral_reply(
                interaction,
                "Закрыть тикет может только участник с **ролью поддержки**.",
            )
            return

        await interaction.response.send_message(
            f"Закрыть тикет **#{ticket.ticket_id}**? Это действие нельзя отменить.",
            view=CloseConfirmView(self, channel_id),
            ephemeral=True,
        )

    async def close_ticket(
        self,
        interaction: discord.Interaction,
        channel_id: int,
    ) -> None:
        if interaction.response.is_done():
            return

        ticket = self.store.get_ticket(channel_id)

        if ticket is None or not ticket.is_open:
            await interaction.response.edit_message(
                content="Тикет уже закрыт или не найден.",
                view=None,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.edit_message(
                content="Не удалось определить участника сервера.",
                view=None,
            )
            return

        if not self._can_manage_ticket(interaction.user, ticket):
            await interaction.response.edit_message(
                content="Закрыть тикет может только администрация проекта",
                view=None,
            )
            return

        updated = self.store.close_ticket(channel_id)
        if updated is None:
            await interaction.response.edit_message(
                content="Не удалось закрыть тикет. Попробуйте ещё раз.",
                view=None,
            )
            return

        ticket_message = await self._fetch_ticket_message(updated)
        if ticket_message is not None:
            embed = self._build_ticket_embed(updated)
            try:
                await ticket_message.edit(embed=embed, view=None)
            except discord.HTTPException as exc:
                logger.warning(
                    "Не удалось обновить сообщение закрытого тикета #%s: %s",
                    ticket.ticket_id,
                    exc,
                )

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException:
                channel = None

        await interaction.response.edit_message(
            content=f"✅ Тикет **#{ticket.ticket_id}** закрыт. Канал будет удалён через несколько секунд.",
            view=None,
        )

        if isinstance(channel, discord.TextChannel):
            try:
                await deliver_ticket_logs(
                    self.bot,
                    self.settings,
                    updated,
                    channel,
                    interaction.user,
                )
            except Exception as exc:
                logger.warning(
                    "Не удалось отправить лог тикета #%s: %s",
                    ticket.ticket_id,
                    exc,
                )

            try:
                await channel.send(
                    f"🔒 Тикет закрыл {interaction.user.mention}. Канал будет удалён."
                )
            except discord.HTTPException:
                pass

            try:
                await channel.delete(reason=f"Тикет #{ticket.ticket_id} закрыт")
            except discord.HTTPException as exc:
                logger.warning(
                    "Не удалось удалить канал тикета #%s: %s",
                    ticket.ticket_id,
                    exc,
                )

        self.store.remove_ticket(channel_id)

    async def restore_state(self) -> None:
        await self.ensure_panel()
        await self.restore_ticket_messages()

    async def refresh_panel(self) -> None:
        await self.ensure_panel()
