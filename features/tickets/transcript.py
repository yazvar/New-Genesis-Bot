from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord

from config.settings import Settings
from features.tickets.embeds import build_ticket_log_embeds
from features.tickets.state import TicketRecord

logger = logging.getLogger(__name__)

MAX_EMBEDS_PER_MESSAGE = 10


async def fetch_channel_messages(
    channel: discord.TextChannel,
) -> list[discord.Message]:
    messages: list[discord.Message] = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append(message)
    return messages


async def _resolve_user(bot: discord.Client, user_id: int) -> discord.User | None:
    user = bot.get_user(user_id)
    if user is not None:
        return user
    try:
        return await bot.fetch_user(user_id)
    except discord.HTTPException:
        logger.warning("Не удалось найти пользователя %s для лога тикета", user_id)
        return None


async def _send_log_dm(
    bot: discord.Client,
    user_id: int,
    embeds: list[discord.Embed],
) -> bool:
    user = await _resolve_user(bot, user_id)
    if user is None:
        return False

    try:
        for index in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            batch = embeds[index : index + MAX_EMBEDS_PER_MESSAGE]
            await user.send(embeds=batch)
    except discord.Forbidden:
        logger.info(
            "Лог тикета не доставлен в ЛС пользователю %s (ЛС закрыты)",
            user_id,
        )
        return False
    except discord.HTTPException as exc:
        logger.warning(
            "Ошибка отправки лога тикета пользователю %s: %s",
            user_id,
            exc,
        )
        return False

    return True


async def deliver_ticket_logs(
    bot: discord.Client,
    settings: Settings,
    ticket: TicketRecord,
    channel: discord.TextChannel,
    closed_by: discord.Member,
) -> None:
    messages = await fetch_channel_messages(channel)
    guild_name = channel.guild.name if channel.guild else None
    closed_at = ticket.closed_at or datetime.now(timezone.utc)

    embeds = build_ticket_log_embeds(
        settings,
        ticket=ticket,
        messages=messages,
        closed_at=closed_at,
        closed_by_id=closed_by.id,
        closed_by_name=closed_by.display_name,
        guild_name=guild_name,
    )

    recipients: list[int] = [ticket.creator_id]
    if ticket.staff_id is not None and ticket.staff_id not in recipients:
        recipients.append(ticket.staff_id)

    for user_id in recipients:
        await _send_log_dm(bot, user_id, embeds)
