from __future__ import annotations

import discord


async def ephemeral_reply(interaction: discord.Interaction, content: str) -> None:
    """Ответ в эфемерном сообщении, даже если interaction уже подтверждён."""
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True)
    else:
        await interaction.response.send_message(content, ephemeral=True)
