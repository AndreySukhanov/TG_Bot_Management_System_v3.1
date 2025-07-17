"""
Модуль для работы с файлами.
Сохраняет документы, фото и другие файлы от пользователей.
"""

import os
import aiofiles
import logging
from datetime import datetime
from typing import Optional
from aiogram.types import Message, Document, PhotoSize
from utils.config import Config

logger = logging.getLogger(__name__)


# Максимальный размер файла в байтах (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


async def save_file(message: Message) -> Optional[str]:
    """
    Сохранение файла из сообщения Telegram
    
    Args:
        message: Сообщение с файлом
        
    Returns:
        Путь к сохраненному файлу или None при ошибке
    """
    config = Config()
    
    try:
        # Создание директории для файлов
        if not os.path.exists(config.FILES_DIR):
            os.makedirs(config.FILES_DIR)
        
        file_info = None
        file_extension = ""
        
        # Обработка документа
        if message.document:
            file_info = message.document
            file_extension = get_file_extension(file_info.file_name)
            logger.info(f"Сохранение документа: {file_info.file_name}")
        
        # Обработка фото
        elif message.photo:
            # Берем фото наилучшего качества
            file_info = message.photo[-1]
            file_extension = ".jpg"
            logger.info(f"Сохранение фото: {file_info.file_id}")
        
        else:
            logger.warning("Неподдерживаемый тип файла")
            return None
        
        # Получение информации о файле
        file = await message.bot.get_file(file_info.file_id)
        
        # Проверка размера файла
        if file.file_size and file.file_size > MAX_FILE_SIZE:
            logger.warning(f"Файл слишком большой: {file.file_size} байт")
            raise ValueError(f"Размер файла превышает максимальный ({MAX_FILE_SIZE // (1024*1024)}MB)")
        
        # Генерация имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id = message.from_user.id
        safe_filename = f"{user_id}_{timestamp}_{file_info.file_id[:8]}{file_extension}"
        
        file_path = os.path.join(config.FILES_DIR, safe_filename)
        
        # Скачивание и сохранение файла
        await message.bot.download_file(file.file_path, file_path)
        
        logger.info(f"Файл сохранен: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Ошибка сохранения файла: {e}")
        return None


def get_file_extension(filename: str) -> str:
    """
    Получение расширения файла
    
    Args:
        filename: Имя файла
        
    Returns:
        Расширение файла с точкой
    """
    if not filename:
        return ""
    
    # Извлечение расширения
    ext = os.path.splitext(filename)[1].lower()
    
    # Проверка на безопасные расширения
    safe_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',  # Изображения
        '.pdf', '.doc', '.docx', '.txt', '.rtf',           # Документы
        '.xls', '.xlsx', '.csv',                           # Таблицы
        '.zip', '.rar', '.7z',                            # Архивы
        '.mp4', '.avi', '.mov', '.wmv'                    # Видео (если нужно)
    }
    
    if ext in safe_extensions:
        return ext
    else:
        logger.warning(f"Потенциально небезопасное расширение: {ext}")
        return ".unknown"


async def delete_file(file_path: str) -> bool:
    """
    Удаление файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        True если файл удален успешно
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Файл удален: {file_path}")
            return True
        else:
            logger.warning(f"Файл не найден: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Ошибка удаления файла {file_path}: {e}")
        return False


def get_file_size(file_path: str) -> int:
    """
    Получение размера файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Размер файла в байтах
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
    except Exception as e:
        logger.error(f"Ошибка получения размера файла {file_path}: {e}")
        return 0


def is_file_exists(file_path: str) -> bool:
    """
    Проверка существования файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        True если файл существует
    """
    return os.path.exists(file_path)


async def cleanup_old_files(days: int = 30):
    """
    Очистка старых файлов
    
    Args:
        days: Количество дней для хранения файлов
    """
    config = Config()
    
    try:
        if not os.path.exists(config.FILES_DIR):
            return
        
        current_time = datetime.now()
        deleted_count = 0
        
        for filename in os.listdir(config.FILES_DIR):
            file_path = os.path.join(config.FILES_DIR, filename)
            
            if os.path.isfile(file_path):
                # Получение времени создания файла
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                
                # Проверка возраста файла
                if (current_time - file_time).days > days:
                    if await delete_file(file_path):
                        deleted_count += 1
        
        logger.info(f"Очищено {deleted_count} старых файлов")
        
    except Exception as e:
        logger.error(f"Ошибка очистки старых файлов: {e}") 