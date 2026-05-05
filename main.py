import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from scheduler import run_scheduler

from handlers.start import router as start_router
from handlers.subscription import router as sub_router
from handlers.payment import router as payment_router
from handlers.config_cmd import router as config_router
from handlers.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env файле!")

    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем роутеры
    dp.include_router(start_router)
    dp.include_router(sub_router)
    dp.include_router(payment_router)
    dp.include_router(config_router)
    dp.include_router(admin_router)

    # Запускаем планировщик в фоне
    asyncio.create_task(run_scheduler(bot))

    logger.info("🍪 CookieVPN бот запущен!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
