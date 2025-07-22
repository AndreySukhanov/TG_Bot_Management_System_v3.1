#!/usr/bin/env python3
"""
Vercel Serverless Function для Telegram Bot
"""
import asyncio
import logging
import os
import sys
import json
from urllib.parse import urlparse, parse_qs

# Добавляем корневую директорию в path для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Настройка логирования для Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные для кеширования
bot = None
dp = None

async def init_bot():
    """Инициализация бота и диспетчера"""
    global bot, dp
    
    if bot is not None and dp is not None:
        return bot, dp
    
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Импортируем модули после установки путей
        from handlers.marketer import setup_marketer_handlers
        from handlers.financier import setup_financier_handlers
        from handlers.manager import setup_manager_handlers
        from handlers.common import setup_common_handlers
        from handlers.menu_handler import setup_menu_handlers
        from handlers.command_handlers import setup_command_handlers
        from handlers.voice_handler import setup_voice_handlers
        from db.database import init_database
        from utils.config import Config
        from utils.bot_commands import BotCommandManager
        
        # Инициализация конфигурации
        config = Config()
        
        # Создание бота и диспетчера
        bot = Bot(token=config.BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        logger.info("Бот создан")
        
        # Инициализация базы данных
        await init_database()
        logger.info("База данных инициализирована")
        
        # Регистрация обработчиков
        setup_common_handlers(dp)
        setup_menu_handlers(dp)
        setup_command_handlers(dp)
        setup_voice_handlers(dp)
        setup_marketer_handlers(dp)
        setup_financier_handlers(dp)
        setup_manager_handlers(dp)
        
        logger.info("Обработчики зарегистрированы")
        
        # Настройка команд бота
        command_manager = BotCommandManager(bot)
        await command_manager.setup_commands()
        
        logger.info("Команды бота настроены")
        
        return bot, dp
        
    except Exception as e:
        logger.error(f"Ошибка инициализации бота: {e}")
        raise

def handler(request, context):
    """Синхронная точка входа для Vercel"""
    return asyncio.run(async_handler(request, context))

async def async_handler(request, context):
    """Асинхронный обработчик запросов"""
    try:
        # Получение данных запроса
        method = request.get('method', 'GET')
        path = request.get('path', '/')
        query_params = request.get('queryStringParameters') or {}
        headers = request.get('headers', {})
        body = request.get('body', '')
        
        logger.info(f"Получен запрос: {method} {path}")
        
        # Health check
        if path in ['/', '/health']:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    "status": "ok", 
                    "bot": "running",
                    "webhook": "active"
                })
            }
        
        # Инициализация бота для всех остальных запросов
        bot_instance, dp_instance = await init_bot()
        
        # Webhook endpoint
        if path == '/webhook' and method == 'POST':
            try:
                # Парсинг JSON данных
                if isinstance(body, str):
                    data = json.loads(body)
                else:
                    data = body
                
                logger.info(f"Получено обновление: {json.dumps(data, ensure_ascii=False)[:200]}...")
                
                # Создание Update объекта и обработка
                from aiogram.types import Update
                update = Update(**data)
                
                # Обработка обновления
                await dp_instance.feed_update(bot_instance, update)
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({"ok": True})
                }
                
            except Exception as e:
                logger.error(f"Ошибка обработки webhook: {e}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        "error": "Webhook processing error", 
                        "details": str(e)
                    })
                }
        
        # Установка webhook
        if path == '/set_webhook':
            try:
                # Получение хоста из заголовков
                host = headers.get('host', headers.get('Host', 'unknown'))
                webhook_url = f"https://{host}/webhook"
                
                result = await bot_instance.set_webhook(webhook_url)
                logger.info(f"Webhook установлен: {webhook_url}")
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        "ok": True, 
                        "webhook_url": webhook_url,
                        "result": result
                    })
                }
            except Exception as e:
                logger.error(f"Ошибка установки webhook: {e}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        "error": "Webhook setup error", 
                        "details": str(e)
                    })
                }
        
        # Получение информации о webhook
        if path == '/webhook_info':
            try:
                info = await bot_instance.get_webhook_info()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        "url": info.url,
                        "has_custom_certificate": info.has_custom_certificate,
                        "pending_update_count": info.pending_update_count,
                        "last_error_date": info.last_error_date,
                        "last_error_message": info.last_error_message,
                        "max_connections": info.max_connections,
                        "allowed_updates": info.allowed_updates
                    })
                }
            except Exception as e:
                logger.error(f"Ошибка получения информации о webhook: {e}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        "error": "Webhook info error", 
                        "details": str(e)
                    })
                }
        
        # 404 для остальных путей
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                "error": "Not found", 
                "path": path
            })
        }
        
    except Exception as e:
        logger.error(f"Критическая ошибка в handler: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                "error": "Internal server error", 
                "details": str(e)
            })
        }