import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)


async def start_health_server() -> None:
    """Мини-сервер для Railway: сервис должен слушать PORT."""
    port_raw = os.getenv("PORT", "").strip()
    if not port_raw:
        return

    port = int(port_raw)
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health-check сервер запущен на порту %s", port)


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")
