from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from discord.ext import commands

logger = logging.getLogger(__name__)

PANEL_HISTORY_LIMIT = 100


@dataclass
class PanelBinding:
    channel_id: int
    message_id: int
    webhook_id: int | None = None


async def fetch_text_channel(
    bot: discord.Client,
    channel_id: int,
) -> discord.TextChannel | None:
    channel = bot.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel

    try:
        fetched = await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        return None

    return fetched if isinstance(fetched, discord.TextChannel) else None


def _pick_keeper(
    candidates: list[discord.Message],
    panel: PanelBinding | None,
    channel_id: int,
    *,
    panel_name: str,
) -> int:
    preferred_id: int | None = None
    if panel is not None and panel.channel_id == channel_id and panel.message_id:
        preferred_id = panel.message_id

    if preferred_id is not None and any(
        message.id == preferred_id for message in candidates
    ):
        return preferred_id

    keeper_id = max(candidates, key=lambda message: message.id).id
    if preferred_id is not None:
        logger.info(
            "Панель «%s»: сохранённое сообщение %s не найдено, используем %s",
            panel_name,
            preferred_id,
            keeper_id,
        )
    return keeper_id


async def _cleanup_bot_panels(
    channel: discord.TextChannel,
    bot: discord.Client,
    panel: PanelBinding | None,
    *,
    panel_name: str,
    panel_title: str | None,
) -> discord.Message | None:
    """Оставляет одно embed-сообщение бота, удаляет дубликаты и старые webhook-панели."""
    bot_user_id = bot.user.id if bot.user else None
    candidates: list[discord.Message] = []
    stale: list[discord.Message] = []

    def _is_panel_message(message: discord.Message) -> bool:
        if panel_title is None:
            return True
        return any(embed.title == panel_title for embed in message.embeds)

    async for message in channel.history(limit=PANEL_HISTORY_LIMIT):
        if not message.embeds or not _is_panel_message(message):
            continue

        if message.webhook_id is not None:
            # Старые панели, отправленные через webhook — кнопки на них
            # больше не работают, удаляем.
            stale.append(message)
            continue

        if bot_user_id is not None and message.author.id == bot_user_id:
            candidates.append(message)

    keeper: discord.Message | None = None
    if candidates:
        keeper_id = _pick_keeper(
            candidates,
            panel,
            channel.id,
            panel_name=panel_name,
        )
        for message in candidates:
            if message.id == keeper_id:
                keeper = message
            else:
                stale.append(message)

    removed = 0
    for message in stale:
        try:
            await message.delete()
            removed += 1
        except discord.HTTPException as exc:
            logger.warning(
                "Панель «%s»: не удалось удалить сообщение %s: %s",
                panel_name,
                message.id,
                exc,
            )

    if removed:
        logger.info(
            "Панель «%s»: удалено лишних сообщений в #%s: %s",
            panel_name,
            channel.name,
            removed,
        )

    return keeper


async def sync_panel(
    bot: commands.Bot,
    *,
    channel_id: int | None,
    webhook_url: str | None,
    webhook_name: str,
    panel: PanelBinding | None,
    set_panel: Callable[[int, int, int | None], None],
    embed: discord.Embed,
    view: discord.ui.View,
) -> PanelBinding | None:
    """Создаёт или обновляет панель с кнопками (сообщение от имени бота).

    Discord не позволяет вешать кнопки на сообщения обычных webhook,
    поэтому панели с кнопками публикуются самим ботом.
    Параметр webhook_url игнорируется.
    """
    if channel_id is None:
        return panel

    channel = await fetch_text_channel(bot, channel_id)
    if channel is None:
        logger.warning(
            "Панель «%s»: канал %s недоступен",
            webhook_name,
            channel_id,
        )
        return panel

    keeper = await _cleanup_bot_panels(
        channel,
        bot,
        panel,
        panel_name=webhook_name,
        panel_title=embed.title,
    )

    if keeper is not None:
        try:
            await keeper.edit(embed=embed, view=view)
            bot.add_view(view, message_id=keeper.id)
            if (
                panel is None
                or panel.channel_id != channel_id
                or panel.message_id != keeper.id
            ):
                set_panel(channel.id, keeper.id, None)
            logger.debug(
                "Панель «%s» обновлена (сообщение %s)",
                webhook_name,
                keeper.id,
            )
            return PanelBinding(channel.id, keeper.id, None)
        except (discord.NotFound, discord.HTTPException) as exc:
            logger.info(
                "Панель «%s» не отредактирована, создаём новую: %s",
                webhook_name,
                exc,
            )

    message = await channel.send(embed=embed, view=view)
    set_panel(channel.id, message.id, None)
    bot.add_view(view, message_id=message.id)

    logger.info(
        "Панель «%s» опубликована в #%s (сообщение %s)",
        webhook_name,
        channel.name,
        message.id,
    )
    return PanelBinding(channel.id, message.id, None)
