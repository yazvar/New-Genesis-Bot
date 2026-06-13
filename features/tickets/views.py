from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from features.tickets.embeds import CATEGORIES, PANEL_CATEGORIES

if TYPE_CHECKING:
    from features.tickets.cog import TicketsCog
    from features.tickets.state import TicketRecord

CUSTOM_CATEGORY_SELECT = "ticket_category_select"
CUSTOM_OPEN_TICKET = "ticket_open_submit"
CUSTOM_ACCEPT_PREFIX = "ticket_accept"
CUSTOM_CLOSE_PREFIX = "ticket_close"
CUSTOM_CLOSE_CONFIRM_PREFIX = "ticket_close_confirm"
CUSTOM_CLOSE_CANCEL_PREFIX = "ticket_close_cancel"


def make_accept_custom_id(channel_id: int) -> str:
    return f"{CUSTOM_ACCEPT_PREFIX}:{channel_id}"


def make_close_custom_id(channel_id: int) -> str:
    return f"{CUSTOM_CLOSE_PREFIX}:{channel_id}"


def make_close_confirm_custom_id(channel_id: int) -> str:
    return f"{CUSTOM_CLOSE_CONFIRM_PREFIX}:{channel_id}"


def make_close_cancel_custom_id(channel_id: int) -> str:
    return f"{CUSTOM_CLOSE_CANCEL_PREFIX}:{channel_id}"


def build_category_select_options() -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for key in PANEL_CATEGORIES:
        cat = CATEGORIES[key]
        options.append(
            discord.SelectOption(
                label=cat["label"][:100],
                value=key,
                description=cat["select_desc"][:100],
                emoji=cat["emoji"],
            )
        )
    return options


class _DisplayOnlyButton(discord.ui.Button):
    """Кнопка для разметки; обработка — через DynamicItem."""

    async def callback(self, interaction: discord.Interaction) -> None:
        return


class _DisplayOnlySelect(discord.ui.Select):
    """Select для разметки; обработка — через DynamicItem."""

    async def callback(self, interaction: discord.Interaction) -> None:
        return


class TicketPanelView(discord.ui.View):
    """Панель подачи тикета: select + кнопки (обработка — DynamicItem)."""

    def __init__(self, cog: TicketsCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

        self.add_item(
            _DisplayOnlySelect(
                custom_id=CUSTOM_CATEGORY_SELECT,
                placeholder="Выберите тему обращения (опционально)",
                min_values=0,
                max_values=1,
                options=build_category_select_options(),
            )
        )
        self.add_item(
            _DisplayOnlyButton(
                label="Открыть тикет",
                style=discord.ButtonStyle.success,
                emoji="🎫",
                custom_id=CUSTOM_OPEN_TICKET,
            )
        )


class TicketModal(discord.ui.Modal, title="Подача тикета"):
    description_input = discord.ui.TextInput(
        label="Описание ситуации",
        placeholder="Опишите обращение как можно подробнее...",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=True,
    )
    player_input = discord.ui.TextInput(
        label="Ник игрока / Steam ID",
        placeholder="Необязательно для проверки базы",
        style=discord.TextStyle.short,
        max_length=200,
        required=False,
    )
    extra_input = discord.ui.TextInput(
        label="Дополнительно",
        placeholder="Время, ссылки на доказательства и т.д.",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    def __init__(self, cog: TicketsCog, category: str) -> None:
        super().__init__()
        self.cog = cog
        self.category = category

    async def on_submit(self, interaction: discord.Interaction) -> None:
        description = self.description_input.value.strip()
        if not description:
            await interaction.response.send_message(
                "Описание не может быть пустым.",
                ephemeral=True,
            )
            return

        player = self.player_input.value.strip() or None
        extra = self.extra_input.value.strip() or None

        await self.cog.create_ticket_from_modal(
            interaction,
            category=self.category,
            form_description=description,
            form_player=player,
            form_extra=extra,
        )


class TicketMessageView(discord.ui.View):
    """Кнопки тикета (обработка — DynamicItem)."""

    def __init__(
        self,
        cog: TicketsCog,
        channel_id: int,
        ticket: TicketRecord | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

        if ticket is None or ticket.is_open:
            if ticket is None or not ticket.is_accepted:
                self.add_item(
                    _DisplayOnlyButton(
                        label="Принять",
                        style=discord.ButtonStyle.success,
                        emoji="✅",
                        custom_id=make_accept_custom_id(channel_id),
                        disabled=ticket is not None and ticket.is_accepted,
                    )
                )
            self.add_item(
                _DisplayOnlyButton(
                    label="Закрыть",
                    style=discord.ButtonStyle.danger,
                    emoji="🔒",
                    custom_id=make_close_custom_id(channel_id),
                )
            )


class CloseConfirmView(discord.ui.View):
    """Подтверждение закрытия тикета (эфемерное сообщение)."""

    def __init__(self, cog: TicketsCog, channel_id: int) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(
        label="Да, закрыть",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.close_ticket(interaction, self.channel_id)

    @discord.ui.button(
        label="Отмена",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Закрытие тикета отменено.",
            view=None,
        )
