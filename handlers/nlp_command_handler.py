"""
Универсальный обработчик команд с поддержкой NLP.
Обрабатывает команды в естественном языке для всех ролей.
"""

import logging
from aiogram.types import Message
from utils.config import Config
from utils.logger import log_action
from nlp.command_parser import CommandNLPParser

logger = logging.getLogger(__name__)


async def nlp_command_handler(message: Message):
    """
    Универсальный обработчик команд с NLP
    Распознает команды в естественном языке и перенаправляет к соответствующим обработчикам
    """
    user_id = message.from_user.id
    config = Config()
    user_role = config.get_user_role(user_id)
    
    # Проверка авторизации
    if user_role == "unknown":
        return
    
    text = message.text
    if not text:
        return
    
    log_action(user_id, "nlp_command_attempt", text)
    
    try:
        # Парсинг команды с помощью NLP
        command_parser = CommandNLPParser()
        command_data = await command_parser.parse_command(text, user_role)
        
        if not command_data:
            # Не является командой, пропускаем
            return
        
        command = command_data["command"]
        confidence = command_data["confidence"]
        
        logger.info(f"Распознана команда '{command}' с уверенностью {confidence} для роли {user_role}")
        log_action(user_id, f"nlp_command_{command}", f"confidence: {confidence}")
        
        # Перенаправление к соответствующим обработчикам
        if command == "start":
            # Динамический импорт для избежания циклических зависимостей
            from handlers.common import start_handler
            await start_handler(message)
        elif command == "help":
            from handlers.common import help_handler
            await help_handler(message)
        elif command == "balance":
            # Проверяем права доступа (только финансисты и руководители)
            if user_role in ["financier", "manager"]:
                if user_role == "manager":
                    from handlers.manager import statistics_handler
                    await statistics_handler(message)  # Руководители получают полную статистику
                else:
                    from handlers.financier import balance_command_handler
                    await balance_command_handler(message)  # Финансисты получают баланс
            else:
                await message.answer(
                    "❌ У вас нет доступа к информации о балансе.\n"
                    "Эта команда доступна только финансистам и руководителям."
                )
        elif command == "stats":
            # Проверяем права доступа (только руководители)
            if user_role == "manager":
                from handlers.manager import statistics_handler
                await statistics_handler(message)
            else:
                await message.answer(
                    "❌ У вас нет доступа к статистике.\n"
                    "Эта команда доступна только руководителям."
                )
        
    except Exception as e:
        logger.error(f"Ошибка обработки NLP команды: {e}")
        # Не отправляем ошибку пользователю, просто логируем


async def smart_message_router(message: Message):
    """
    Умный роутер сообщений
    Определяет тип сообщения и направляет к соответствующему обработчику
    """
    user_id = message.from_user.id
    config = Config()
    user_role = config.get_user_role(user_id)
    
    if user_role == "unknown":
        return
    
    text = message.text
    if not text:
        return
    
    # Сначала проверяем, является ли это командой
    command_parser = CommandNLPParser()
    command_data = await command_parser.parse_command(text, user_role)
    
    if command_data:
        # Это команда - обрабатываем через NLP command handler
        await nlp_command_handler(message)
        return True  # Сообщение обработано
    
    # Если не команда, возвращаем False чтобы другие обработчики могли обработать
    return False