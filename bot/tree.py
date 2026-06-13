from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import require_guild_administrator


class AdministratorCommandTree(app_commands.CommandTree[commands.Bot]):
    """Slash-команды только для участников с правом Administrator."""

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        return await require_guild_administrator(interaction)
