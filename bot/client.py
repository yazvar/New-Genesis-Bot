import logging

import aiohttp
import discord
from discord.ext import commands, tasks

from bot.health import start_health_server
from bot.persistent_ui import register_dynamic_items
from bot.tree import AdministratorCommandTree
from config.paths import DATA_DIR
from config.settings import Settings
from utils.permissions import ADMIN_REQUIRED_MESSAGE, member_has_administrator
from features.tickets import TicketsCog

logger = logging.getLogger(__name__)


class GenesisBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=AdministratorCommandTree,
        )
        self.settings = settings
        self._state_restored = False
        self.add_check(self._administrator_only_check)

    async def _administrator_only_check(self, ctx: commands.Context) -> bool:
        """Префикс-команды (!) — только участники с правом Administrator."""
        if ctx.guild is None:
            await ctx.send("Команда доступна только на сервере.")
            return False

        if not isinstance(ctx.author, discord.Member):
            await ctx.send("Не удалось определить участника сервера.")
            return False

        if member_has_administrator(ctx.author):
            return True

        await ctx.send(ADMIN_REQUIRED_MESSAGE)
        return False

    async def setup_hook(self) -> None:
        await start_health_server()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Данные бота хранятся в %s", DATA_DIR.resolve())

        await self.add_cog(TicketsCog(self, self.settings))
        register_dynamic_items(self)

        self.panel_sync_loop.change_interval(
            seconds=self.settings.panel_sync_interval
        )

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(
                "Slash-команды синхронизированы для сервера %s",
                self.settings.guild_id,
            )
        else:
            await self.tree.sync()
            logger.info("Slash-команды синхронизированы глобально")

    async def _ensure_bot_avatar(self) -> None:
        """Устанавливает аватар бота из BOT_AVATAR_URL, если аватар ещё не задан."""
        if self.user is None or self.user.avatar is not None:
            return

        url = self.settings.bot_avatar_url
        if not url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.read()
            await self.user.edit(avatar=data)
            logger.info("Аватар бота установлен из %s", url)
        except Exception as exc:
            logger.warning("Не удалось установить аватар бота: %s", exc)

    async def _sync_all_panels(self) -> None:
        tickets_cog = self.get_cog("TicketsCog")
        if isinstance(tickets_cog, TicketsCog):
            await tickets_cog.ensure_panel()

    async def _restore_persistent_state(self) -> None:
        tickets_cog = self.get_cog("TicketsCog")
        if isinstance(tickets_cog, TicketsCog):
            await tickets_cog.restore_state()
            if tickets_cog.store.panel:
                logger.info("Панель тикетов восстановлена")
            if tickets_cog.store.open_tickets:
                logger.info(
                    "Тикеты восстановлены: %s открытых",
                    len(tickets_cog.store.open_tickets),
                )

    async def on_ready(self) -> None:
        logger.info(
            "Бот запущен как %s (id=%s)",
            self.user,
            self.user.id if self.user else "?",
        )

        if not self._state_restored:
            await self._ensure_bot_avatar()
            await self._restore_persistent_state()
            self._state_restored = True
            logger.info("Панель и кнопки восстановлены после перезапуска")

        if not self.panel_sync_loop.is_running():
            self.panel_sync_loop.start()

    async def close(self) -> None:
        if self.panel_sync_loop.is_running():
            self.panel_sync_loop.cancel()
        await super().close()

    @tasks.loop(seconds=30)
    async def panel_sync_loop(self) -> None:
        await self._sync_all_panels()

    @panel_sync_loop.before_loop
    async def _before_panel_sync(self) -> None:
        await self.wait_until_ready()

    @panel_sync_loop.error
    async def _panel_sync_error(self, error: BaseException) -> None:
        logger.exception("Ошибка цикла проверки панелей: %s", error)


def create_bot(settings: Settings) -> GenesisBot:
    return GenesisBot(settings)
