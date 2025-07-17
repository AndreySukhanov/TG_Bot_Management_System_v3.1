"""
Скрипт для обновления команд бота
Обновляет меню команд для всех пользователей
"""

import asyncio
import sys
import os

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot
from utils.config import Config
from utils.bot_commands import BotCommandManager

async def update_commands():
    """Обновление команд для всех пользователей"""
    print("Обновление команд бота...")
    
    # Инициализация
    config = Config()
    bot = Bot(token=config.BOT_TOKEN)
    command_manager = BotCommandManager(bot)
    
    try:
        # Обновляем команды по умолчанию
        await command_manager.set_default_commands()
        print("Команды по умолчанию обновлены")
        
        # Обновляем команды для всех пользователей
        await command_manager.update_all_user_commands()
        print("Команды для всех пользователей обновлены")
        
        print("\nКоманды для руководителей:")
        manager_commands = command_manager.get_commands_for_role("manager")
        for cmd in manager_commands:
            print(f"  {cmd.command} - {cmd.description}")
        
        print("\nОбновление завершено!")
        
    except Exception as e:
        print(f"Ошибка при обновлении команд: {e}")
    
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(update_commands())