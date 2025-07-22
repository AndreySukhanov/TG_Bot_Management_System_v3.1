from http.server import BaseHTTPRequestHandler
import json
import asyncio
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None

async def init_simple_bot():
    """Минимальная инициализация бота"""
    global bot
    
    if bot is not None:
        return bot
    
    try:
        from aiogram import Bot
        
        # Получаем токен из переменных окружения
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise Exception("BOT_TOKEN не найден в переменных окружения")
        
        bot = Bot(token=bot_token)
        logger.info("Простой бот создан")
        return bot
        
    except Exception as e:
        logger.error(f"Ошибка инициализации простого бота: {e}")
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
                    "bot": "simple_running",
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
            
            # Webhook endpoint - простая обработка
            if self.path == '/webhook':
                result = asyncio.run(self._handle_simple_webhook())
                self._send_response(200, result)
                return
            
            # 404 для остальных путей
            self._send_response(404, {"error": "Not found", "path": self.path})
            
        except Exception as e:
            logger.error(f"Ошибка POST запроса: {e}")
            self._send_response(500, {"error": str(e)})
    
    async def _handle_simple_webhook(self):
        """Простая обработка webhook"""
        try:
            # Получение данных запроса
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            logger.info(f"Получено обновление: {json.dumps(data, ensure_ascii=False)[:200]}...")
            
            # Простой ответ на сообщения
            if 'message' in data and 'text' in data['message']:
                bot_instance = await init_simple_bot()
                chat_id = data['message']['chat']['id']
                await bot_instance.send_message(chat_id, "Бот работает! Получено сообщение: " + data['message']['text'])
            
            return {"ok": True}
            
        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}")
            return {"ok": False, "error": str(e)}
    
    async def _set_webhook(self):
        """Установка webhook"""
        try:
            from aiogram import Bot
            
            # Получаем токен
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                raise Exception("BOT_TOKEN не найден")
            
            # Создаем новый экземпляр бота для этой операции
            temp_bot = Bot(token=bot_token)
            
            host = self.headers.get('host', self.headers.get('Host', 'unknown'))
            webhook_url = f"https://{host}/webhook"
            
            # Устанавливаем webhook
            result = await temp_bot.set_webhook(webhook_url)
            logger.info(f"Webhook установлен: {webhook_url}")
            
            # Закрываем сессию
            await temp_bot.session.close()
            
            return {
                "ok": True, 
                "webhook_url": webhook_url,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
            return {"ok": False, "error": str(e)}
    
    async def _get_webhook_info(self):
        """Получение информации о webhook"""
        try:
            from aiogram import Bot
            
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                raise Exception("BOT_TOKEN не найден")
            
            temp_bot = Bot(token=bot_token)
            info = await temp_bot.get_webhook_info()
            
            await temp_bot.session.close()
            
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
            return {"ok": False, "error": str(e)}
    
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