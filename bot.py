"""
Главный файл Telegram-бота для автоматизации запросов на оплату.
Обрабатывает заявки от маркетологов и управляет балансом.
"""

import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.marketer import setup_marketer_handlers
from handlers.financier import setup_financier_handlers
from handlers.manager import setup_manager_handlers
from handlers.common import setup_common_handlers
from handlers.menu_handler import setup_menu_handlers
from handlers.command_handlers import setup_command_handlers
from handlers.voice_handler import setup_voice_handlers
from db.database import init_database
from utils.config import Config
from utils.logger import setup_logger
from utils.bot_commands import BotCommandManager


async def main():
    """Основная функция запуска бота"""
    # Настройка логирования
    setup_logger()
    logger = logging.getLogger(__name__)
    
    # Инициализация конфигурации
    config = Config()
    
    # Проверка конфигурации
    if not config.validate_config():
        logger.error("Некорректная конфигурация. Остановка запуска бота.")
        return
    
    # Создание бота и диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Инициализация базы данных
    await init_database()
    logger.info("База данных инициализирована")
    
    # Регистрация обработчиков (ВАЖЕН ПОРЯДОК!)
    setup_voice_handlers(dp)      # ПЕРВЫМИ! Голосовые сообщения должны обрабатываться до common
    setup_command_handlers(dp)
    setup_marketer_handlers(dp)
    setup_financier_handlers(dp)
    setup_manager_handlers(dp)
    setup_menu_handlers(dp)
    setup_common_handlers(dp)     # ПОСЛЕДНИМИ! Чтобы не перехватывать специфические команды
    
    logger.info("Обработчики зарегистрированы")
    
    # Настройка команд бота
    command_manager = BotCommandManager(bot)
    await command_manager.set_default_commands()
    await command_manager.update_all_user_commands()
    
    logger.info("Команды бота настроены")
    
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main()) 