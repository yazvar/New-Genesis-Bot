from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    guild_id: int | None
    bot_avatar_url: str | None
    panel_sync_interval: int
    ticket_panel_channel_id: int | None
    ticket_category_id: int | None
    ticket_staff_role_ids: tuple[int, ...]
    ticket_max_per_user: int
    ticket_brand_name: str
    ticket_panel_title: str
    ticket_panel_description: str
    ticket_thumbnail_url: str | None


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "DISCORD_TOKEN не задан. Скопируйте .env.example в .env и укажите токен."
        )

    guild_raw = os.getenv("GUILD_ID", "").strip()
    guild_id = int(guild_raw) if guild_raw else None

    sync_interval = int(os.getenv("PANEL_SYNC_INTERVAL", "30"))
    if sync_interval < 15:
        sync_interval = 15

    brand_name = os.getenv("TICKET_BRAND_NAME", "New Genesis").strip() or "New Genesis"

    return Settings(
        discord_token=token,
        guild_id=guild_id,
        bot_avatar_url=_optional_str("BOT_AVATAR_URL"),
        panel_sync_interval=sync_interval,
        ticket_panel_channel_id=_optional_int("TICKET_PANEL_CHANNEL_ID"),
        ticket_category_id=_optional_int("TICKET_CATEGORY_ID"),
        ticket_staff_role_ids=_parse_int_list("TICKET_STAFF_ROLE_ID"),
        ticket_max_per_user=max(1, int(os.getenv("TICKET_MAX_PER_USER", "3"))),
        ticket_brand_name=brand_name,
        ticket_panel_title=os.getenv("TICKET_PANEL_TITLE", "Центр поддержки"),
        ticket_panel_description=os.getenv(
            "TICKET_PANEL_DESCRIPTION",
            "Выберите тип обращения кнопкой ниже. Мы создадим приватный канал, "
            "где будете только вы и администрация проекта.",
        ),
        ticket_thumbnail_url=_optional_str("TICKET_THUMBNAIL_URL"),
    )


def _optional_int(name: str, *, default: int | None = None) -> int | None:
    raw = os.getenv(name, "").strip()
    if raw:
        return int(raw)
    return default


def _optional_str(name: str) -> str | None:
    raw = os.getenv(name, "").strip()
    return raw or None


def _parse_int_list(
    name: str,
    *,
    default: tuple[int, ...] = (),
) -> tuple[int, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())
