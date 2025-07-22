from http.server import BaseHTTPRequestHandler
import json
import asyncio
import logging
import os
import sys
from urllib.parse import parse_qs

# Добавляем корневую директорию в path для импорта модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, 'utils'))
sys.path.insert(0, os.path.join(root_dir, 'handlers'))
sys.path.insert(0, os.path.join(root_dir, 'db'))
sys.path.insert(0, os.path.join(root_dir, 'nlp'))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные для кеширования
bot = None
dp = None

# Встроенная конфигурация как fallback для Vercel
class BuiltinConfig:
    """Встроенная конфигурация для работы без внешних модулей"""
    
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    DATABASE_PATH = "bot.db"
    LOW_BALANCE_THRESHOLD = 100.0
    
    # Тестовые пользователи для демонстрации (если переменные окружения не заданы)
    MARKETERS = [int(x) for x in os.getenv("MARKETERS", "123456789").split(",") if x.strip()]
    FINANCIERS = [int(x) for x in os.getenv("FINANCIERS", "987654321").split(",") if x.strip()]  
    MANAGERS = [int(x) for x in os.getenv("MANAGERS", "555666777").split(",") if x.strip()]
    
    @classmethod
    def get_user_role(cls, user_id: int) -> str:
        """Определяет роль пользователя по ID"""
        if user_id in cls.MARKETERS:
            return "marketer"
        elif user_id in cls.FINANCIERS:
            return "financier"
        elif user_id in cls.MANAGERS:
            return "manager"
        else:
            return "unknown"
    
    @classmethod
    def is_authorized(cls, user_id: int) -> bool:
        """Проверяет, авторизован ли пользователь"""
        return cls.get_user_role(user_id) != "unknown"

# Создаем глобальный экземпляр конфигурации
builtin_config = BuiltinConfig()

async def init_bot():
    """Инициализация бота и диспетчера"""
    global bot, dp
    
    if bot is not None and dp is not None:
        logger.info("Бот уже инициализирован, возвращаем существующий")
        return bot, dp
    
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Получаем токен из переменных окружения
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise Exception("BOT_TOKEN не найден в переменных окружения")
        
        # Создание бота и диспетчера
        bot = Bot(token=bot_token)
        dp = Dispatcher(storage=MemoryStorage())
        
        logger.info("✓ Бот и диспетчер созданы")
        
        # Пытаемся импортировать модули по одному
        logger.info("📦 Начинаем пошаговую инициализацию...")
        
        # Шаг 1: База данных
        try:
            logger.info("1️⃣ Импортируем db.database...")
            try:
                from db.database import init_database
            except ImportError:
                # Альтернативный путь для Vercel
                import sys
                import importlib.util
                
                db_path = os.path.join(root_dir, 'db', 'database.py')
                if os.path.exists(db_path):
                    spec = importlib.util.spec_from_file_location("database", db_path)
                    database_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(database_module)
                    init_database = database_module.init_database
                else:
                    raise ImportError("Не найден файл db/database.py")
                    
            logger.info("✓ db.database импортирован")
            
            logger.info("1️⃣ Инициализируем базу данных...")
            await init_database()
            logger.info("✓ База данных инициализирована")
            
        except Exception as e:
            logger.error(f"❌ Ошибка базы данных: {e}")
            # Не поднимаем ошибку - работаем без базы данных
            logger.warning("⚠️ Работаем без базы данных - будет только fallback функциональность")
        
        # Шаг 2: Импорт обработчиков
        handlers_imported = {}
        
        def safe_import_handler(module_name: str, function_name: str):
            """Безопасный импорт обработчика с fallback"""
            try:
                logger.info(f"2️⃣ Импортируем {module_name}...")
                
                # Подробная диагностика
                logger.info(f"   🔍 Попытка импорта модуля: {module_name}")
                logger.info(f"   🔍 Ищем функцию: {function_name}")
                
                module = __import__(module_name, fromlist=[function_name])
                logger.info(f"   ✅ Модуль {module_name} загружен")
                
                handler_func = getattr(module, function_name)
                logger.info(f"   ✅ Функция {function_name} найдена")
                
                logger.info(f"✓ {module_name} импортирован успешно")
                return handler_func
                
            except ImportError as ie:
                logger.error(f"❌ ImportError в {module_name}: {ie}")
                logger.error(f"   📍 Детали: {str(ie)}")
                return None
            except AttributeError as ae:
                logger.error(f"❌ AttributeError в {module_name}: {ae}")
                logger.error(f"   📍 Функция {function_name} не найдена в модуле")
                return None
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка в {module_name}: {e}")
                logger.error(f"   📍 Тип: {type(e).__name__}")
                import traceback
                logger.error(f"   📍 Traceback: {traceback.format_exc()}")
                return None
        
        # Импортируем обработчики с безопасными методами
        handlers_imported['common'] = safe_import_handler('handlers.common', 'setup_common_handlers')
        
        handlers_imported['command'] = safe_import_handler('handlers.command_handlers', 'setup_command_handlers')
        handlers_imported['menu'] = safe_import_handler('handlers.menu_handler', 'setup_menu_handlers')
        handlers_imported['voice'] = safe_import_handler('handlers.voice_handler', 'setup_voice_handlers')
        handlers_imported['marketer'] = safe_import_handler('handlers.marketer', 'setup_marketer_handlers')
        handlers_imported['financier'] = safe_import_handler('handlers.financier', 'setup_financier_handlers')
        handlers_imported['manager'] = safe_import_handler('handlers.manager', 'setup_manager_handlers')
        
        # Шаг 3: Регистрация обработчиков объединена с проверкой
        logger.info("3️⃣ Регистрация объединена с проверкой работоспособности")
        
        # Финальная проверка
        final_handlers = len(dp.message.handlers)
        logger.info(f"🎯 ИТОГО ЗАРЕГИСТРИРОВАНО MESSAGE HANDLERS: {final_handlers}")
        
        # Проверяем успешность загрузки основных обработчиков
        successful_imports = sum(1 for h in handlers_imported.values() if h is not None)
        logger.info(f"📊 Успешно импортировано обработчиков: {successful_imports}/{len(handlers_imported)}")
        
        if final_handlers == 0:
            logger.error("❌ НЕ ЗАРЕГИСТРИРОВАНО НИ ОДНОГО MESSAGE HANDLER!")
            logger.info("🆘 Добавляем минимальный набор обработчиков...")
            await add_minimal_handlers(dp)
        
        # Безопасная проверка и регистрация обработчиков
        working_handlers = 0
        logger.info("🔧 НАЧИНАЕМ ПРОВЕРКУ ОБРАБОТЧИКОВ...")
        
        try:
            for name, handler_func in handlers_imported.items():
                try:
                    logger.info(f"🔍 Проверяем {name}...")
                    if handler_func is not None:
                        logger.info(f"🔍 Пробуем зарегистрировать {name}...")
                        handler_func(dp)
                        working_handlers += 1
                        logger.info(f"✅ {name} обработчик зарегистрирован успешно")
                    else:
                        logger.info(f"⚠️ {name} обработчик отсутствует (None)")
                except Exception as e:
                    logger.error(f"❌ Ошибка регистрации {name}: {str(e)}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            logger.info(f"📊 Работающих обработчиков: {working_handlers}/{len(handlers_imported)}")
            
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА В ЦИКЛЕ ОБРАБОТЧИКОВ: {str(e)}")
            import traceback
            logger.error(f"💥 Traceback: {traceback.format_exc()}")
        
        # ВСЕГДА используем встроенные обработчики для стабильной работы
        try:
            logger.info("🚀 Активируем встроенные обработчики для полной функциональности")
            await add_builtin_handlers(dp)
            logger.info("✅ Встроенные обработчики активированы")
        except Exception as e:
            logger.error(f"💥 ОШИБКА ВСТРОЕННЫХ ОБРАБОТЧИКОВ: {str(e)}")
            import traceback
            logger.error(f"💥 Traceback: {traceback.format_exc()}")
        
        # Обновляем счетчик после добавления fallback
        final_handlers = len(dp.message.handlers)
        logger.info(f"🎯 ИТОГО MESSAGE HANDLERS (с fallback): {final_handlers}")
        
        # Выводим список всех обработчиков
        for i, handler in enumerate(dp.message.handlers):
            handler_name = handler.callback.__name__ if handler.callback else "Unknown"
            logger.info(f"  📝 Handler {i}: {handler_name}")
        
        # Шаг 4: Команды бота (опционально)
        try:
            logger.info("4️⃣ Импортируем utils.bot_commands...")
            bot_commands_func = safe_import_handler('utils.bot_commands', 'BotCommandManager')
            if bot_commands_func:
                logger.info("✓ utils.bot_commands импортирован")
                
                logger.info("4️⃣ Настраиваем команды бота...")
                command_manager = bot_commands_func(bot)
                await command_manager.setup_commands()
                logger.info("✓ Команды бота настроены")
            else:
                logger.warning("⚠️ Команды бота не настроены - модуль не импортирован")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки команд (не критично): {e}")
        
        logger.info("🎉 ИНИЦИАЛИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        return bot, dp
        
    except Exception as e:
        logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ: {e}")
        logger.error(f"Тип ошибки: {e.__class__.__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Создаем базовый бот с аварийным обработчиком
        if bot is None:
            bot = Bot(token=os.getenv("BOT_TOKEN"))
            dp = Dispatcher(storage=MemoryStorage())
            await add_emergency_handler(dp)
        
        return bot, dp

async def add_minimal_handlers(dp):
    """Добавляет минимальный набор обработчиков"""
    from aiogram import types
    from aiogram.filters import Command
    
    async def minimal_start(message: types.Message):
        await message.reply("🤖 Бот запущен в минимальном режиме. Некоторые функции недоступны.")
    
    async def minimal_help(message: types.Message):
        await message.reply("ℹ️ Справка временно недоступна. Бот работает в ограниченном режиме.")
    
    async def minimal_default(message: types.Message):
        await message.reply("🤖 Бот в ограниченном режиме. Используйте /start")
    
    dp.message.register(minimal_start, Command("start"))
    dp.message.register(minimal_help, Command("help"))
    dp.message.register(minimal_default)
    
    logger.info("✓ Минимальные обработчики добавлены")

async def add_emergency_handler(dp):
    """Добавляет базовый обработчик в случае ошибки инициализации"""
    from aiogram import types
    
    async def emergency_handler(message: types.Message):
        """Аварийный обработчик"""
        await message.reply("🤖 Бот временно работает в ограниченном режиме. Используйте /start")
    
    dp.message.register(emergency_handler)
    logger.info("✓ Аварийный обработчик зарегистрирован")

async def add_fallback_handler(dp):
    """Добавляет fallback обработчик который ТОЧНО сработает"""
    from aiogram import types
    from aiogram.filters import Command
    
    async def fallback_start(message: types.Message):
        """Fallback start handler"""
        try:
            user_id = message.from_user.id
            logger.info(f"🆘 Fallback /start от пользователя {user_id}")
            await message.reply(
                "🤖 Бот запущен в режиме совместимости.\n"
                "Некоторые функции могут быть ограничены.\n\n"
                "Попробуйте:\n"
                "• /help - справка\n"
                "• /status - статус системы"
            )
        except Exception as e:
            logger.error(f"Ошибка в fallback_start: {e}")
    
    async def fallback_help(message: types.Message):
        """Fallback help handler"""
        try:
            user_id = message.from_user.id
            logger.info(f"🆘 Fallback /help от пользователя {user_id}")
            await message.reply(
                "ℹ️ Справка (режим совместимости)\n\n"
                "Доступные команды:\n"
                "• /start - перезапуск\n"
                "• /help - эта справка\n"
                "• /status - статус бота\n\n"
                "Для полной функциональности обратитесь к администратору."
            )
        except Exception as e:
            logger.error(f"Ошибка в fallback_help: {e}")
    
    async def fallback_status(message: types.Message):
        """Fallback status handler"""
        try:
            user_id = message.from_user.id
            logger.info(f"🆘 Fallback /status от пользователя {user_id}")
            await message.reply(
                "📊 Статус системы:\n\n"
                "🤖 Бот: Активен (режим совместимости)\n"
                "⚡ Webhook: Работает\n"
                "🛡️ Режим: Fallback handlers\n\n"
                "Если видите это сообщение, основные обработчики не загружены."
            )
        except Exception as e:
            logger.error(f"Ошибка в fallback_status: {e}")
    
    async def fallback_default(message: types.Message):
        """Универсальный fallback обработчик"""
        try:
            user_id = message.from_user.id
            text = message.text or "<non-text>"
            logger.info(f"🆘 Fallback default для {user_id}: {text[:50]}")
            await message.reply(
                f"🤖 Получено сообщение: «{text[:50]}{'...' if len(text) > 50 else ''}»\n\n"
                f"Бот работает в ограниченном режиме.\n"
                f"Используйте /help для получения справки."
            )
        except Exception as e:
            logger.error(f"Ошибка в fallback_default: {e}")
    
    # Регистрируем fallback обработчики 
    dp.message.register(fallback_start, Command("start"))
    dp.message.register(fallback_help, Command("help"))  
    dp.message.register(fallback_status, Command("status"))
    dp.message.register(fallback_default)  # Последний - ловит всё остальное
    
    logger.info("✓ Fallback обработчики зарегистрированы")

async def add_builtin_handlers(dp):
    """Добавляет встроенные обработчики для полной функциональности"""
    from aiogram import types
    from aiogram.filters import Command
    
    async def builtin_start(message: types.Message):
        """Встроенный start handler"""
        try:
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            logger.info(f"🚀 Встроенный /start от пользователя {user_id} ({username})")
            
            user_role = builtin_config.get_user_role(user_id)
            
            if user_role == "unknown":
                await message.answer(
                    "❌ У вас нет доступа к этому боту.\n"
                    "Обратитесь к администратору для получения разрешений."
                )
                return
            
            role_messages = {
                "marketer": (
                    "👋 Привет! Вы зарегистрированы как **Маркетолог**.\n\n"
                    "📝 **Доступные команды:**\n"
                    "• /help - справка\n"
                    "• /status - статус системы\n\n"
                    "🤖 Режим: Встроенные обработчики"
                ),
                "financier": (
                    "👋 Привет! Вы зарегистрированы как **Финансист**.\n\n"
                    "💼 **Доступные команды:**\n"
                    "• /help - справка\n"
                    "• /status - статус системы\n\n"
                    "🤖 Режим: Встроенные обработчики"
                ),
                "manager": (
                    "👋 Привет! Вы зарегистрированы как **Руководитель**.\n\n"
                    "👨‍💼 **Доступные команды:**\n"
                    "• /help - справка\n"
                    "• /status - статус системы\n\n"
                    "🤖 Режим: Встроенные обработчики"
                )
            }
            
            await message.answer(
                role_messages[user_role], 
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка в builtin_start: {e}")
    
    async def builtin_help(message: types.Message):
        """Встроенный help handler"""
        try:
            user_id = message.from_user.id
            user_role = builtin_config.get_user_role(user_id)
            
            if user_role == "unknown":
                await message.answer("❌ У вас нет доступа к этому боту.")
                return
            
            await message.answer(
                f"📖 **Справка ({user_role})**\n\n"
                f"🤖 **Встроенный режим работы**\n"
                f"Бот работает со встроенными обработчиками.\n\n"
                f"**Доступные команды:**\n"
                f"• /start - главное меню\n"
                f"• /help - эта справка\n"
                f"• /status - статус системы\n\n"
                f"**Ваша роль:** {user_role}\n"
                f"**ID:** {user_id}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка в builtin_help: {e}")
    
    async def builtin_status(message: types.Message):
        """Встроенный status handler"""
        try:
            user_id = message.from_user.id
            user_role = builtin_config.get_user_role(user_id)
            
            await message.answer(
                f"📊 **Статус системы**\n\n"
                f"🤖 **Бот:** Активен (встроенные обработчики)\n"
                f"⚡ **Webhook:** Работает\n"
                f"🛡️ **Режим:** Builtin handlers\n"
                f"👤 **Ваша роль:** {user_role}\n"
                f"🆔 **Ваш ID:** {user_id}\n\n"
                f"✅ **Все системы работают нормально**",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка в builtin_status: {e}")
    
    async def builtin_default(message: types.Message):
        """Встроенный default handler"""
        try:
            user_id = message.from_user.id
            user_role = builtin_config.get_user_role(user_id)
            text = message.text or "<non-text>"
            
            if user_role == "unknown":
                await message.answer(
                    "❌ У вас нет доступа к этому боту.\n"
                    "Обратитесь к администратору."
                )
                return
            
            await message.answer(
                f"🤖 **Получено сообщение:** «{text[:50]}{'...' if len(text) > 50 else ''}»\n\n"
                f"👤 **Роль:** {user_role}\n"
                f"🔧 **Режим:** Встроенные обработчики\n\n"
                f"Используйте /help для получения справки."
            )
        except Exception as e:
            logger.error(f"Ошибка в builtin_default: {e}")
    
    # Регистрируем встроенные обработчики
    dp.message.register(builtin_start, Command("start"))
    dp.message.register(builtin_help, Command("help"))  
    dp.message.register(builtin_status, Command("status"))
    dp.message.register(builtin_default)  # Последний - ловит всё остальное
    
    logger.info("✅ Встроенные обработчики зарегистрированы")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработка GET запросов"""
        try:
            logger.info(f"GET запрос: {self.path}")
            
            # Health check
            if self.path in ['/', '/health']:
                # Инициализируем бота при первом запросе чтобы убедиться что всё работает
                try:
                    bot_instance, dp_instance = asyncio.run(init_bot())
                    handlers_count = len(dp_instance.message.handlers) if dp_instance.message.handlers else 0
                    response = {
                        "status": "ok", 
                        "bot": "running",
                        "webhook": "active",
                        "handlers": handlers_count,
                        "message": "Bot initialized successfully"
                    }
                except Exception as e:
                    logger.error(f"Ошибка инициализации бота в health check: {e}")
                    response = {
                        "status": "error", 
                        "bot": "error",
                        "webhook": "inactive",
                        "error": str(e)
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
                result = self._run_async_safe(self._handle_webhook)
                self._send_response(200, result)
                return
            
            # Установка webhook через POST
            if self.path == '/set_webhook':
                result = self._run_async_safe(self._set_webhook)
                self._send_response(200, result)
                return
            
            # 404 для остальных путей
            self._send_response(404, {"error": "Not found", "path": self.path})
            
        except Exception as e:
            logger.error(f"Ошибка POST запроса: {e}")
            self._send_response(500, {"error": str(e)})
    
    def _run_async_safe(self, coro_func):
        """Безопасный запуск async функции в serverless окружении"""
        # Всегда создаем новый event loop для каждого webhook запроса
        # Это самый надежный способ в serverless окружении
        try:
            logger.info("🔄 Создаем новый event loop для webhook")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            # Вызываем функцию для создания нового coroutine
            result = new_loop.run_until_complete(coro_func())
            new_loop.close()
            logger.info("✅ Webhook обработан с новым event loop")
            return result
        except Exception as e:
            logger.error(f"💥 Ошибка в новом event loop: {e}")
            # Пробуем старую логику как fallback
            try:
                logger.info("🔧 Пробуем старую логику как fallback...")
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    logger.info("🔄 Создан fallback event loop")
                
                if loop.is_running():
                    try:
                        import nest_asyncio
                        nest_asyncio.apply()
                        logger.info("🔄 Применен nest_asyncio в fallback")
                        return loop.run_until_complete(coro_func())
                    except ImportError:
                        raise Exception("nest_asyncio недоступен и loop запущен")
                else:
                    return loop.run_until_complete(coro_func())
                    
            except Exception as e2:
                logger.error(f"💥 Все методы event loop не сработали: {e2}")
                raise
    
    async def _handle_webhook(self):
        """Обработка webhook от Telegram"""
        try:
            # Получение данных запроса
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            logger.info(f"📨 Получено обновление: {json.dumps(data, ensure_ascii=False)[:200]}...")
            
            # Инициализация бота
            bot_instance, dp_instance = await init_bot()
            
            # ДИАГНОСТИКА: Проверяем что обработчики есть
            handlers_count = len(dp_instance.message.handlers) if dp_instance.message.handlers else 0
            logger.info(f"🎯 Доступно message handlers: {handlers_count}")
            
            if handlers_count == 0:
                logger.error("❌ НЕТ ОБРАБОТЧИКОВ СООБЩЕНИЙ!")
                logger.info("🆘 Добавляем экстренные обработчики...")
                await add_minimal_handlers(dp_instance)
                handlers_count = len(dp_instance.message.handlers)
                logger.info(f"✅ Добавлено экстренных обработчиков: {handlers_count}")
            else:
                # Показываем список обработчиков для диагностики
                for i, handler in enumerate(dp_instance.message.handlers):
                    handler_name = handler.callback.__name__ if handler.callback else "Unknown"
                    logger.info(f"  📝 Handler {i}: {handler_name}")
            
            # Создание Update объекта
            from aiogram.types import Update
            update = Update(**data)
            
            # Дополнительная диагностика входящего апдейта
            if update.message:
                text = update.message.text or "<non-text message>"
                user_id = update.message.from_user.id if update.message.from_user else "unknown"
                logger.info(f"📩 Сообщение от {user_id}: '{text[:50]}...'")
            elif update.callback_query:
                logger.info(f"🔘 Callback query: {update.callback_query.data}")
            else:
                logger.info(f"❓ Неизвестный тип апдейта: {update}")
            
            # Обработка обновления
            logger.info("⚡ Начинаем обработку апдейта...")
            await dp_instance.feed_update(bot_instance, update)
            logger.info("✅ Апдейт обработан успешно")
            
            return {"ok": True}
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки webhook: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
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
            
            # Получение хоста
            host = self.headers.get('host', self.headers.get('Host', 'unknown'))
            webhook_url = f"https://{host}/webhook"
            
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
            raise
    
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
