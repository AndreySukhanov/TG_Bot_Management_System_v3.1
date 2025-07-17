"""
Модуль настройки логирования.
Настраивает логгеры для консоли и файла.
"""

import logging
import os
from datetime import datetime
from utils.config import Config


def setup_logger():
    """Настройка логирования"""
    config = Config()
    
    # Создание директории для логов
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Удаление существующих обработчиков
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для файла
    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def log_action(user_id: int, action: str, details: str = ""):
    """Логирование действий пользователей"""
    logger = logging.getLogger("user_actions")
    logger.info(f"User {user_id}: {action} - {details}") 