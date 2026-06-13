from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from config.settings import Settings

if TYPE_CHECKING:
    from features.tickets.state import TicketRecord

COLOR_PANEL = 0x5865F2
COLOR_TICKET = 0xFEE75C
COLOR_TICKET_ACCEPTED = 0x57F287
COLOR_TICKET_CLOSED = 0x99AAB5

CATEGORIES: dict[str, dict[str, str]] = {
    "cheats": {
        "label": "Читы / Подозрение на софт",
        "emoji": "🚨",
        "title": "Читы / Подозрение на софт",
        "field": "🚨 Читы",
        "field_desc": "Подача жалобы на подозрительного игрока",
        "select_desc": "Подача жалобы на подозрительного игрока",
        "instructions": (
            "Опишите ситуацию, укажите ник подозреваемого и приложите доказательства."
        ),
    },
    "relog": {
        "label": "Релог с файла / во время рейда",
        "emoji": "⚔️",
        "title": "Релог с файла / во время рейда",
        "field": "⚔️ Релог",
        "field_desc": "Выход с сервера в обход правил",
        "select_desc": "Выход с сервера в обход правил",
        "instructions": (
            "Укажите ник нарушителя, время инцидента и приложите доказательства."
        ),
    },
    "raid_rules": {
        "label": "Нарушение правил рейда",
        "emoji": "🔸",
        "title": "Нарушение правил рейда",
        "field": "🔸 Рейд",
        "field_desc": "Нарушение правил рейда",
        "select_desc": "Нарушение правил рейда",
        "instructions": (
            "Опишите нарушение, укажите участников и приложите доказательства."
        ),
    },
    "player_report": {
        "label": "Прочая жалоба на игрока",
        "emoji": "👤",
        "title": "Прочая жалоба на игрока",
        "field": "👤 Жалоба",
        "field_desc": "Любая другая жалоба на игрока",
        "select_desc": "Любая другая жалоба на игрока",
        "instructions": (
            "Опишите ситуацию, укажите ник игрока и приложите доказательства."
        ),
    },
    "base_check": {
        "label": "Проверка базы (строительство)",
        "emoji": "🏗️",
        "title": "Проверка базы (строительство)",
        "field": "🏗️ База",
        "field_desc": "Проверка постройки на соответствие правилам",
        "select_desc": "Проверка постройки на соответствие правилам",
        "instructions": (
            "Укажите координаты или описание базы и суть обращения."
        ),
    },
    # legacy (для старых тикетов в базе)
    "bug": {
        "label": "Баг",
        "emoji": "🐞",
        "title": "Сообщение об ошибке",
        "field": "🐞 Баг",
        "field_desc": "Ошибки, поломки, проблемы сервера.",
        "select_desc": "Ошибки, поломки, проблемы сервера.",
        "instructions": (
            "Опишите, что произошло, когда это случилось, "
            "и приложите скриншоты или логи, если они есть."
        ),
    },
    "help": {
        "label": "Помощь",
        "emoji": "🛟",
        "title": "Запрос помощи",
        "field": "🛟 Помощь",
        "field_desc": "Вопросы, поддержка, просьбы.",
        "select_desc": "Вопросы, поддержка, просьбы.",
        "instructions": "Опишите свой вопрос или проблему как можно подробнее.",
    },
    "report": {
        "label": "Репорт",
        "emoji": "⚠️",
        "title": "Репорт на игрока",
        "field": "⚠️ Репорт",
        "field_desc": "Жалоба на игрока или ситуацию.",
        "select_desc": "Жалоба на игрока или ситуацию.",
        "instructions": (
            "Укажи ник игрока, время, суть нарушения и приложи доказательства."
        ),
    },
    "other": {
        "label": "Прочее",
        "emoji": "📌",
        "title": "Прочее обращение",
        "field": "📌 Прочее",
        "field_desc": "Все, что не подходит выше.",
        "select_desc": "Все, что не подходит выше.",
        "instructions": "Опишите суть обращения.",
    },
}

PANEL_CATEGORIES: tuple[str, ...] = ("bug", "help", "report", "other")

DEFAULT_PANEL_CATEGORY = "other"


def get_category(category: str) -> dict[str, str]:
    return CATEGORIES.get(category, CATEGORIES["other"])


def build_panel_embed(settings: Settings) -> discord.Embed:
    now = datetime.now(timezone.utc)
    brand = settings.ticket_brand_name

    embed = discord.Embed(
        title=settings.ticket_panel_title,
        description=settings.ticket_panel_description,
        color=COLOR_PANEL,
        timestamp=now,
    )
    embed.set_author(name=f"{brand} • Ticket Center")

    for key in PANEL_CATEGORIES:
        cat = CATEGORIES[key]
        embed.add_field(
            name=cat["field"],
            value=cat["field_desc"],
            inline=True,
        )

    embed.add_field(
        name="Лимит",
        value=f"До **{settings.ticket_max_per_user}** активных тикетов на пользователя.",
        inline=False,
    )

    if settings.ticket_thumbnail_url:
        embed.set_thumbnail(url=settings.ticket_thumbnail_url)

    embed.set_footer(
        text="Выберите категорию обращения • ответ придет в созданном канале"
    )
    return embed


def build_ticket_embed(
    settings: Settings,
    *,
    ticket_id: int,
    category: str,
    creator_id: int,
    creator_name: str,
    staff_id: int | None = None,
    staff_name: str | None = None,
    closed_at: datetime | None = None,
    created_at: datetime | None = None,
    form_description: str | None = None,
    form_player: str | None = None,
    form_extra: str | None = None,
) -> discord.Embed:
    now = created_at or datetime.now(timezone.utc)
    brand = settings.ticket_brand_name
    cat = get_category(category)

    if closed_at is not None:
        status = "Закрыт"
        color = COLOR_TICKET_CLOSED
    elif staff_id is not None:
        status = "Принят"
        color = COLOR_TICKET_ACCEPTED
    else:
        status = "Открыт"
        color = COLOR_TICKET

    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['title']}",
        description=(
            f"Здравствуйте, <@{creator_id}>. Администрация уже получила уведомление.\n\n"
            f"{cat['instructions']}"
        ),
        color=color,
        timestamp=now,
    )
    embed.set_author(name=f"{brand} • Ticket #{ticket_id}")

    embed.add_field(name="Номер", value=f"#{ticket_id}", inline=True)
    embed.add_field(name="Категория", value=cat["label"], inline=True)
    embed.add_field(name="Статус", value=status, inline=True)
    embed.add_field(
        name="Создатель",
        value=f"<@{creator_id}> (`{creator_name}`)",
        inline=False,
    )

    if form_description:
        embed.add_field(
            name="Описание",
            value=form_description[:1024],
            inline=False,
        )

    if form_player:
        embed.add_field(
            name="Ник / Steam ID",
            value=form_player[:1024],
            inline=False,
        )

    if form_extra:
        embed.add_field(
            name="Дополнительно",
            value=form_extra[:1024],
            inline=False,
        )

    if staff_id is not None and staff_name:
        embed.add_field(
            name="Принял",
            value=f"<@{staff_id}> (`{staff_name}`)",
            inline=False,
        )
    else:
        embed.add_field(name="Принял", value="Ожидает персонал", inline=False)

    if settings.ticket_thumbnail_url:
        embed.set_thumbnail(url=settings.ticket_thumbnail_url)

    embed.set_footer(text="Принять и закрыть тикет может только администрация проекта")
    return embed


EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_VALUE_LIMIT = 1024


def _format_log_timestamp(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M")


def _format_log_message(message: discord.Message) -> str:
    author = message.author
    name = author.display_name if isinstance(author, discord.Member) else str(author)
    time_label = _format_log_timestamp(message.created_at)

    body_parts: list[str] = []
    if message.content:
        body_parts.append(message.content)

    for attachment in message.attachments:
        body_parts.append(f"📎 {attachment.filename}: {attachment.url}")

    for embed in message.embeds:
        title = embed.title or "Embed"
        if embed.description:
            snippet = embed.description.strip()[:300]
            body_parts.append(f"📋 {title}: {snippet}")
        else:
            body_parts.append(f"📋 {title}")

    if message.stickers:
        body_parts.append(f"🎭 Стикер: {message.stickers[0].name}")

    body = "\n".join(body_parts) if body_parts else "—"

    line = f"**{name}** · {time_label}\n{body}"
    if len(line) > EMBED_FIELD_VALUE_LIMIT:
        line = line[: EMBED_FIELD_VALUE_LIMIT - 3] + "..."
    return line


def _chunk_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def _build_transcript_embeds(messages: list[discord.Message]) -> list[discord.Embed]:
    if not messages:
        embed = discord.Embed(
            title="💬 Переписка",
            description="Сообщений в канале не было.",
            color=COLOR_TICKET_CLOSED,
        )
        return [embed]

    lines = [_format_log_message(message) for message in messages]
    packed: list[str] = []
    current = ""

    for line in lines:
        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{line}"
        if len(candidate) <= EMBED_DESCRIPTION_LIMIT:
            current = candidate
            continue

        if current:
            packed.append(current)
        if len(line) <= EMBED_DESCRIPTION_LIMIT:
            current = line
        else:
            packed.extend(_chunk_text(line, EMBED_DESCRIPTION_LIMIT))
            current = ""

    if current:
        packed.append(current)

    total = len(packed)
    embeds: list[discord.Embed] = []
    for index, description in enumerate(packed, start=1):
        title = "💬 Переписка" if total == 1 else f"💬 Переписка ({index}/{total})"
        embeds.append(
            discord.Embed(
                title=title,
                description=description,
                color=COLOR_TICKET_CLOSED,
            )
        )
    return embeds


def build_ticket_log_embeds(
    settings: Settings,
    *,
    ticket: TicketRecord,
    messages: list[discord.Message],
    closed_at: datetime,
    closed_by_id: int,
    closed_by_name: str,
    guild_name: str | None,
) -> list[discord.Embed]:
    brand = settings.ticket_brand_name
    cat = get_category(ticket.category)

    summary = discord.Embed(
        title=f"📋 Лог тикета #{ticket.ticket_id}",
        description="Тикет закрыт. Ниже — данные обращения и полная переписка.",
        color=COLOR_TICKET_CLOSED,
        timestamp=closed_at,
    )
    summary.set_author(name=f"{brand} • Ticket Log")

    if guild_name:
        summary.add_field(name="Сервер", value=guild_name, inline=True)
    summary.add_field(name="Категория", value=cat["label"], inline=True)
    summary.add_field(name="Сообщений", value=str(len(messages)), inline=True)
    summary.add_field(
        name="Создатель",
        value=f"<@{ticket.creator_id}> (`{ticket.creator_name}`)",
        inline=False,
    )

    if ticket.staff_id is not None and ticket.staff_name:
        summary.add_field(
            name="Принял",
            value=f"<@{ticket.staff_id}> (`{ticket.staff_name}`)",
            inline=True,
        )
    else:
        summary.add_field(name="Принял", value="—", inline=True)

    summary.add_field(
        name="Закрыл",
        value=f"<@{closed_by_id}> (`{closed_by_name}`)",
        inline=True,
    )
    summary.add_field(
        name="Создан",
        value=_format_log_timestamp(ticket.created_at),
        inline=True,
    )
    summary.add_field(
        name="Закрыт",
        value=_format_log_timestamp(closed_at),
        inline=True,
    )

    if settings.ticket_thumbnail_url:
        summary.set_thumbnail(url=settings.ticket_thumbnail_url)

    return [summary, *_build_transcript_embeds(messages)]
