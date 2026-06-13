from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ui import Button, DynamicItem, Select

from features.tickets.views import (
    CUSTOM_ACCEPT_PREFIX,
    CUSTOM_CATEGORY_SELECT,
    CUSTOM_CLOSE_PREFIX,
    CUSTOM_OPEN_TICKET,
    build_category_select_options,
    make_accept_custom_id,
    make_close_custom_id,
)

if TYPE_CHECKING:
    from features.tickets.cog import TicketsCog


def _get_cog(client: discord.Client) -> TicketsCog | None:
    cog = client.get_cog("TicketsCog")
    return cog if cog is not None else None


class TicketCategorySelectDynamic(
    DynamicItem[Select],
    template=rf"^{CUSTOM_CATEGORY_SELECT}$",
):
    def __init__(self, cog: TicketsCog) -> None:
        super().__init__(
            Select(
                custom_id=CUSTOM_CATEGORY_SELECT,
                placeholder="Выберите тему обращения (опционально)",
                min_values=0,
                max_values=1,
                options=build_category_select_options(),
            ),
        )
        self.cog = cog

    @classmethod
    async def from_custom_id(
        cls,
        interaction,
        item,
        match,
        /,
    ) -> TicketCategorySelectDynamic:
        cog = _get_cog(interaction.client)
        if cog is None:
            raise RuntimeError("TicketsCog не загружен")
        return cls(cog)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return
        values = interaction.data.get("values", []) if interaction.data else []
        category = values[0] if values else None
        self.cog.set_selected_category(interaction.user.id, category)
        if category is None:
            await interaction.response.send_message(
                "Тема обращения сброшена.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Тема обращения выбрана. Нажмите **«Открыть тикет»**.",
                ephemeral=True,
            )


class OpenTicketSubmitDynamic(
    DynamicItem[Button],
    template=rf"^{CUSTOM_OPEN_TICKET}$",
):
    def __init__(self, cog: TicketsCog) -> None:
        super().__init__(
            Button(
                label="Открыть тикет",
                style=discord.ButtonStyle.success,
                emoji="🎫",
                custom_id=CUSTOM_OPEN_TICKET,
            ),
        )
        self.cog = cog

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /) -> OpenTicketSubmitDynamic:
        cog = _get_cog(interaction.client)
        if cog is None:
            raise RuntimeError("TicketsCog не загружен")
        return cls(cog)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return
        await self.cog.show_ticket_modal(interaction)


class AcceptTicketDynamic(
    DynamicItem[Button],
    template=rf"^{CUSTOM_ACCEPT_PREFIX}:(?P<channel_id>\d+)$",
):
    def __init__(
        self,
        cog: TicketsCog,
        channel_id: int,
        *,
        disabled: bool,
    ) -> None:
        super().__init__(
            Button(
                label="Принять",
                style=discord.ButtonStyle.success,
                emoji="✅",
                custom_id=make_accept_custom_id(channel_id),
                disabled=disabled,
            ),
        )
        self.cog = cog
        self.channel_id = channel_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /) -> AcceptTicketDynamic:
        cog = _get_cog(interaction.client)
        if cog is None:
            raise RuntimeError("TicketsCog не загружен")

        channel_id = int(match["channel_id"])
        ticket = cog.store.get_ticket(channel_id)
        disabled = ticket is not None and ticket.is_accepted
        return cls(cog, channel_id, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return
        await self.cog.accept_ticket(interaction, self.channel_id)


class CloseTicketDynamic(
    DynamicItem[Button],
    template=rf"^{CUSTOM_CLOSE_PREFIX}:(?P<channel_id>\d+)$",
):
    def __init__(self, cog: TicketsCog, channel_id: int) -> None:
        super().__init__(
            Button(
                label="Закрыть",
                style=discord.ButtonStyle.danger,
                emoji="🔒",
                custom_id=make_close_custom_id(channel_id),
            ),
        )
        self.cog = cog
        self.channel_id = channel_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /) -> CloseTicketDynamic:
        cog = _get_cog(interaction.client)
        if cog is None:
            raise RuntimeError("TicketsCog не загружен")
        return cls(cog, int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return
        await self.cog.request_close_ticket(interaction, self.channel_id)
