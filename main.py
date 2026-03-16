import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PORT
from database import init_db
from api import app
from handlers import all_routers
from services.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main():
    # ── инициализация БД ──
    await init_db()
    log.info("Database initialized")

    # ── бот ──
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    for router in all_routers:
        dp.include_router(router)
    log.info(f"Registered {len(all_routers)} routers")

    # ── передаём бот в FastAPI ──
    app.state.bot = bot

    # ── планировщик ──
    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("Scheduler started")

    # ── запускаем бот (polling) + API (uvicorn) параллельно ──
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    )

    log.info(f"Starting bot polling + API server on port {PORT}")

    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())