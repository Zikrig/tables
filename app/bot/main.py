"""Точка входа Telegram-бота"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.managers.config_manager import SupplierConfigManager
from app.managers.user_manager import UserManager
from app.scheduler.notification_scheduler import NotificationScheduler


load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

ACCESS_PASSWORD = os.getenv('ACCESS_PASSWORD', '123')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

config_manager = SupplierConfigManager()
user_manager = UserManager()
notification_scheduler: NotificationScheduler | None = None

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Импортируем обработчики (они используют dp/bot/config_manager от сюда)
from app.bot import handlers  # noqa: E402,F401


async def main():
    global notification_scheduler
    logger.info("Запуск бота...")
    notification_scheduler = NotificationScheduler(bot, config_manager, user_manager)
    scheduler_task = asyncio.create_task(notification_scheduler.start())
    try:
        await dp.start_polling(bot)
    finally:
        notification_scheduler.stop()
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())


