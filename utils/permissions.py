from __future__ import annotations

import discord

ADMIN_REQUIRED_MESSAGE = (
    "Эту команду могут использовать только участники с правом **Администратор** "
    "(роль с включённой опцией «Администратор»)."
)


def member_has_administrator(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


async def require_guild_administrator(interaction: discord.Interaction) -> bool:
    """Проверка для slash-команд: только право Administrator на сервере."""
    if interaction.guild is None:
        await _deny(interaction, "Команда доступна только на сервере.")
        return False

    if not isinstance(interaction.user, discord.Member):
        await _deny(interaction, "Не удалось определить участника сервера.")
        return False

    if member_has_administrator(interaction.user):
        return True

    await _deny(interaction, ADMIN_REQUIRED_MESSAGE)
    return False


async def _deny(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
