from http.server import BaseHTTPRequestHandler
import json
import asyncio
import logging
import os
import sys
from urllib.parse import parse_qs

# Добавляем корневую директорию в path для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Настройка логирования
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработка GET запросов"""
        try:
            logger.info(f"GET запрос: {self.path}")
            
            # Health check
            if self.path in ['/', '/health']:
                response = {
                    "status": "ok", 
                    "bot": "running",
                    "webhook": "active"
                }
                self._send_response(200, response)
                return
            
            # Установка webhook
            if self.path == '/set_webhook':
                result = asyncio.run(self._set_webhook())
                self._send_response(200, result)
                return
            
            # Информация о webhook
            if self.path == '/webhook_info':
                result = asyncio.run(self._get_webhook_info())
                self._send_response(200, result)
                return
            
            # 404 для остальных путей
            self._send_response(404, {"error": "Not found", "path": self.path})
            
        except Exception as e:
            logger.error(f"Ошибка GET запроса: {e}")
            self._send_response(500, {"error": str(e)})
    
    def do_POST(self):
        """Обработка POST запросов"""
        try:
            logger.info(f"POST запрос: {self.path}")
            
            # Webhook endpoint
            if self.path == '/webhook':
                result = asyncio.run(self._handle_webhook())
                self._send_response(200, result)
                return
            
            # Установка webhook через POST
            if self.path == '/set_webhook':
                result = asyncio.run(self._set_webhook())
                self._send_response(200, result)
                return
            
            # 404 для остальных путей
            self._send_response(404, {"error": "Not found", "path": self.path})
            
        except Exception as e:
            logger.error(f"Ошибка POST запроса: {e}")
            self._send_response(500, {"error": str(e)})
    
    async def _handle_webhook(self):
        """Обработка webhook от Telegram"""
        try:
            # Получение данных запроса
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            logger.info(f"Получено обновление: {json.dumps(data, ensure_ascii=False)[:200]}...")
            
            # Инициализация бота
            bot_instance, dp_instance = await init_bot()
            
            # Создание Update объекта и обработка
            from aiogram.types import Update
            update = Update(**data)
            
            # Обработка обновления
            await dp_instance.feed_update(bot_instance, update)
            
            return {"ok": True}
            
        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}")
            raise
    
    async def _set_webhook(self):
        """Установка webhook"""
        try:
            # Инициализация бота
            bot_instance, _ = await init_bot()
            
            # Получение хоста
            host = self.headers.get('host', self.headers.get('Host', 'unknown'))
            webhook_url = f"https://{host}/webhook"
            
            result = await bot_instance.set_webhook(webhook_url)
            logger.info(f"Webhook установлен: {webhook_url}")
            
            return {
                "ok": True, 
                "webhook_url": webhook_url,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
            raise
    
    async def _get_webhook_info(self):
        """Получение информации о webhook"""
        try:
            # Инициализация бота
            bot_instance, _ = await init_bot()
            
            info = await bot_instance.get_webhook_info()
            return {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
                "max_connections": info.max_connections,
                "allowed_updates": info.allowed_updates
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о webhook: {e}")
            raise
    
    def _send_response(self, status_code, data):
        """Отправка JSON ответа"""
        try:
            response_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")