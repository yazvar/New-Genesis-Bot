"""Регистрация persistent UI (панели и dynamic-кнопки) при старте бота."""

from __future__ import annotations

import logging

from discord.ext import commands

from features.tickets.dynamic_items import (
    AcceptTicketDynamic,
    CloseTicketDynamic,
    OpenTicketSubmitDynamic,
    TicketCategorySelectDynamic,
)

logger = logging.getLogger(__name__)

DYNAMIC_ITEMS = (
    TicketCategorySelectDynamic,
    OpenTicketSubmitDynamic,
    AcceptTicketDynamic,
    CloseTicketDynamic,
)


def register_dynamic_items(bot: commands.Bot) -> None:
    bot.add_dynamic_items(*DYNAMIC_ITEMS)
    logger.info(
        "Зарегистрированы dynamic-кнопки: %s",
        ", ".join(item.__name__ for item in DYNAMIC_ITEMS),
    )
