import os
import tempfile
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, Voice
from openai import AsyncOpenAI

from utils.config import Config
import logging

logger = logging.getLogger(__name__)
router = Router()

class VoiceProcessor:
    def __init__(self):
        self.config = Config()
        self.openai_client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        
    async def process_voice_message(self, voice: Voice, bot) -> Optional[str]:
        try:
            print(f"[VOICE] Получение файла голосового сообщения...")
            voice_file = await bot.get_file(voice.file_id)
            print(f"[VOICE] Файл получен: {voice_file.file_path}, размер: {voice.file_size} байт")
            
            print(f"[VOICE] Создание временного файла...")
            with tempfile.NamedTemporaryFile(suffix='.oga', delete=False) as temp_file:
                await bot.download_file(voice_file.file_path, temp_file)
                temp_file_path = temp_file.name
            
            print(f"[VOICE] Файл сохранен в: {temp_file_path}")
            print(f"[VOICE] Отправка в Whisper API...")
            
            with open(temp_file_path, 'rb') as audio_file:
                transcript = await self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"
                )
            
            print(f"[VOICE] Whisper API ответ получен")
            os.unlink(temp_file_path)
            print(f"[VOICE] Временный файл удален")
            
            return transcript.text
            
        except Exception as e:
            print(f"[VOICE ERROR] Ошибка при обработке голосового сообщения: {e}")
            logger.error(f"Ошибка при обработке голосового сообщения: {e}")
            # Удаляем временный файл если он был создан
            try:
                if 'temp_file_path' in locals():
                    os.unlink(temp_file_path)
                    print(f"[VOICE] Временный файл удален после ошибки")
            except:
                pass
            return None

    async def _handle_voice_payment_request(self, message, parsed_data):
        """Обработка голосовой заявки на оплату для маркетологов"""
        try:
            from db.database import PaymentDB, BalanceDB
            
            amount = parsed_data.get("amount")
            platform = parsed_data.get("platform")
            if not platform or not platform.strip():
                platform = "Не указано"
            project = parsed_data.get("project")
            if not project or not project.strip():
                project = "Не указан" 
            payment_method = parsed_data.get("payment_method")
            if not payment_method or not payment_method.strip():
                payment_method = "Не указан"
            payment_details = parsed_data.get("payment_details")
            description = parsed_data.get("description", "")
            
            if not amount or amount <= 0:
                await message.answer(
                    "❌ Не удалось определить сумму платежа.\n"
                    "Попробуйте сказать более четко: 'Нужна оплата Фейсбук на 100 долларов'"
                )
                return
            
            # Проверка баланса
            current_balance = await BalanceDB.get_balance()
            
            if current_balance < amount:
                await message.answer(
                    f"❌ <b>Недостаточно средств на балансе!</b>\n\n"
                    f"💰 Текущий баланс: <b>{current_balance:.2f}$</b>\n"
                    f"💸 Запрашиваемая сумма: <b>{amount:.2f}$</b>\n"
                    f"📉 Нехватка: <b>{amount - current_balance:.2f}$</b>\n\n"
                    f"Обратитесь к руководителю для пополнения баланса.",
                    parse_mode="HTML"
                )
                return
            
            # Создание заявки
            payment_id = await PaymentDB.create_payment(
                marketer_id=message.from_user.id,
                service_name=platform,
                amount=amount,
                payment_method=payment_method,
                payment_details=payment_details or "",
                project_name=project
            )
            
            # Отправка подтверждения маркетологу
            await message.answer(
                f"✅ <b>Заявка создана!</b>\n\n"
                f"🆔 ID заявки: <b>{payment_id}</b>\n"
                f"💰 Сумма: <b>{amount}$</b>\n"
                f"📱 Платформа: <b>{platform}</b>\n"
                f"📋 Проект: <b>{project}</b>\n"
                f"💳 Способ оплаты: <b>{payment_method}</b>\n"
                f"📝 Описание: {description}\n\n"
                f"📤 Финансистам отправлено уведомление для обработки.",
                parse_mode="HTML"
            )
            
            # Уведомление финансистов
            from handlers.marketer import notify_financiers_about_payment
            await notify_financiers_about_payment(
                message.bot, 
                payment_id, 
                {
                    'amount': amount,
                    'service_name': platform,
                    'project_name': project,
                    'payment_method': payment_method,
                    'payment_details': payment_details or ""
                }
            )
            
        except Exception as e:
            logger.error(f"Ошибка создания голосовой заявки: {e}")
            await message.answer("❌ Произошла ошибка при создании заявки. Попробуйте еще раз.")
    
    async def _handle_voice_payment_confirm(self, message, parsed_data):
        """Обработка голосового подтверждения оплаты для финансистов"""
        try:
            from db.database import PaymentDB, BalanceDB
            
            payment_id = parsed_data.get("payment_id")
            description = parsed_data.get("description", "")
            
            if not payment_id:
                await message.answer(
                    "❌ Не удалось определить ID заявки для подтверждения.\n"
                    "Попробуйте сказать: 'Оплачено 123'"
                )
                return
            
            # Проверка существования платежа
            payment = await PaymentDB.get_payment(payment_id)
            if not payment:
                await message.answer(
                    f"❌ Заявка с ID <code>{payment_id}</code> не найдена.",
                    parse_mode="HTML"
                )
                return
            
            if payment["status"] != "pending":
                await message.answer(
                    f"❌ Заявка <code>{payment_id}</code> уже обработана.\n"
                    f"Текущий статус: <b>{payment['status']}</b>",
                    parse_mode="HTML"
                )
                return
            
            # Списание средств с баланса
            current_balance = await BalanceDB.get_balance()
            payment_amount = float(payment["amount"])
            
            if current_balance < payment_amount:
                await message.answer(
                    f"❌ <b>Недостаточно средств для подтверждения!</b>\n\n"
                    f"💰 Текущий баланс: <b>{current_balance:.2f}$</b>\n"
                    f"💸 Сумма заявки: <b>{payment_amount:.2f}$</b>\n"
                    f"📉 Нехватка: <b>{payment_amount - current_balance:.2f}$</b>",
                    parse_mode="HTML"
                )
                return
            
            # Обновление статуса заявки
            await PaymentDB.update_payment_status(payment_id, "paid")
            
            # Списание с баланса
            new_balance = current_balance - payment_amount
            await BalanceDB.subtract_balance(
                payment_amount,
                payment_id,
                f"Оплата заявки #{payment_id} ({payment['platform']} - {payment['project']})"
            )
            
            # Подтверждение финансисту
            await message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"🆔 ID заявки: <b>{payment_id}</b>\n"
                f"💰 Сумма: <b>{payment_amount:.2f}$</b>\n"
                f"📱 Платформа: <b>{payment['platform']}</b>\n"
                f"📋 Проект: <b>{payment['project']}</b>\n"
                f"💳 Способ: <b>{payment['payment_method']}</b>\n\n"
                f"💰 Баланс: <b>{current_balance:.2f}$</b> → <b>{new_balance:.2f}$</b>\n"
                f"📤 Маркетологу отправлено уведомление.",
                parse_mode="HTML"
            )
            
            # Уведомление маркетолога
            from handlers.financier import notify_marketer_payment_confirmed
            await notify_marketer_payment_confirmed(
                message.bot,
                payment["user_id"],
                payment_id,
                payment
            )
            
            # Проверка низкого баланса
            config = Config()
            if new_balance < config.LOW_BALANCE_THRESHOLD:
                from handlers.financier import notify_managers_low_balance
                await notify_managers_low_balance(message.bot)
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения голосовой оплаты: {e}")
            await message.answer("❌ Произошла ошибка при подтверждении оплаты. Попробуйте еще раз.")
    
    async def _handle_voice_ai_analytics(self, message, parsed_data, original_query):
        """Обработка голосовых AI-аналитических запросов для руководителей"""
        try:
            description = parsed_data.get("description", "")
            
            # Используем либо описание из ИИ-агента, либо оригинальный распознанный текст
            query = original_query.strip()
            
            logger.info(f"Обрабатываем AI-аналитический запрос: {query}")
            
            try:
                # Отправляем запрос в AI-помощник менеджера
                from nlp.manager_ai_assistant import process_manager_query
                
                # Уведомляем пользователя о начале обработки
                await message.answer("🤖 Анализирую данные, момент...")
                
                response = await process_manager_query(query)
                
                # Отправляем ответ пользователя
                await message.answer(
                    f"🤖 <b>AI-Аналитик:</b>\n\n{response}",
                    parse_mode="HTML"
                )
            except ImportError as e:
                logger.error(f"Модуль AI-аналитики не найден: {e}")
                await message.answer(
                    "❌ AI-аналитика временно недоступна.\n"
                    "Используйте текстовые команды или обратитесь к администратору."
                )
            except Exception as e:
                logger.error(f"Ошибка AI-аналитики: {e}")
                await message.answer(
                    "❌ Произошла ошибка при анализе данных.\n"
                    "Попробуйте переформулировать вопрос или обратитесь к администратору."
                )
            
        except Exception as e:
            logger.error(f"Ошибка голосового AI-аналитического запроса: {e}")
            await message.answer(
                "❌ Произошла ошибка при анализе данных.\n"
                "Попробуйте переформулировать вопрос или обратитесь к администратору."
            )
    
    async def _handle_voice_ai_help(self, message, user_role: str):
        """Обработка голосовой команды AI-помощника - показываем справку"""
        if user_role == "manager":
            await message.answer(
                "🤖 <b>AI-Помощник активирован!</b>\n\n"
                "<b>Примеры голосовых запросов:</b>\n"
                "• 'Сколько человек в команде?'\n"
                "• 'Какой сейчас баланс?'\n"
                "• 'Платежи за неделю'\n"
                "• 'Покажи ожидающие оплаты'\n"
                "• 'Последние операции'\n"
                "• 'История баланса'\n"
                "• 'Статистика по платформам'\n\n"
                "<b>Или используйте текстовую команду:</b>\n"
                "• <code>/ai Ваш вопрос</code>\n\n"
                "Просто задайте голосовой вопрос!",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ AI-помощник доступен только руководителям.")

    def _get_voice_suggestions_for_role(self, user_role: str) -> str:
        """Возвращает подсказки голосовых команд для конкретной роли"""
        suggestions = {
            "manager": [
                "👨‍💼 <b>Руководитель:</b>",
                "• 'Покажи статистику' - полная аналитика системы",
                "• 'Покажи баланс' - текущий баланс и операции", 
                "• 'Сколько человек в команде?' - AI-аналитика",
                "• 'Какие платежи были на этой неделе?' - AI-анализ",
                "• 'История баланса' - AI-отчет",
                "• 'Пополни баланс на 1000' - пополнение баланса",
                "• 'Обнули баланс' - сброс баланса к нулю", 
                "• 'Дашборд' - ссылка на веб-интерфейс",
                "• 'ИИ помощник' - запуск AI-аналитика",
                "• 'Помощь' - справочная информация"
            ],
            "financier": [
                "💰 <b>Финансист:</b>",
                "• 'Оплачено 123' - подтверждение оплаты заявки",
                "• 'Покажи баланс' - текущий баланс системы",
                "• 'Последние операции' - история платежей",
                "• 'Помощь' - справочная информация"
            ],
            "marketer": [
                "📱 <b>Маркетолог:</b>",
                "• 'Нужна оплата Фейсбук 100 долларов проект Альфа' - заявка на оплату",
                "• 'Оплати Гугл Адс 250$ через карту' - создание заявки",
                "• 'Требуется оплата Инстаграм для проекта Бета' - новая заявка",
                "• 'Помощь' - справочная информация"
            ]
        }
        
        role_suggestions = suggestions.get(user_role, ["• 'Помощь' - справочная информация"])
        return "\n".join(role_suggestions)

voice_processor = VoiceProcessor()

@router.message(F.voice)
async def handle_voice_message(message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "unknown"
        print(f"[VOICE] Получено голосовое сообщение от {user_id} ({username})")
        logger.info(f"Получено голосовое сообщение от пользователя {user_id}")
        
        print(f"[VOICE] Начинаем транскрипцию...")
        transcription = await voice_processor.process_voice_message(message.voice, message.bot)
        print(f"[VOICE] Результат транскрипции: {transcription}")
        logger.info(f"Transcription result: {transcription}")
        
        if transcription:
            logger.info(f"Распознан текст от пользователя {user_id}: {transcription}")
            
            await message.reply(
                f"🎤 Распознано: {transcription}\n\n"
                f"📝 Обрабатываю как текстовое сообщение...",
                parse_mode="HTML"
            )
            logger.info("Отправлен ответ с результатом распознавания")
            
            # Используем универсальный ИИ-агент для обработки команд
            try:
                logger.info("Анализируем распознанный текст через универсальный ИИ-агент")
                
                user_id = message.from_user.id
                config = Config()
                user_role = config.get_user_role(user_id)
                
                # Импортируем универсальный ИИ-агент
                from nlp.universal_ai_parser import UniversalAIParser
                
                ai_parser = UniversalAIParser()
                parsed_data = await ai_parser.parse_message(transcription, user_role)
                
                if parsed_data:
                    operation_type = parsed_data["operation_type"]
                    confidence = parsed_data.get("confidence", 0)
                    
                    print(f"[VOICE] ИИ-агент результат: operation_type='{operation_type}', confidence={confidence}")
                    print(f"[VOICE] Полные данные от ИИ: {parsed_data}")
                    logger.info(f"ИИ-агент распознал операцию '{operation_type}' с уверенностью {confidence}")
                    
                    # Если уверенность низкая, предупреждаем пользователя
                    if confidence < 0.7:
                        await message.answer(
                            f"🤖 Распознано: '{transcription}'\n"
                            f"⚠️ Не совсем уверен в понимании (уверенность: {confidence:.0%})\n\n"
                            f"Попробуйте переформулировать или напишите текстом для большей точности."
                        )
                        return
                    
                    # Обрабатываем операции в зависимости от роли и типа
                    if operation_type == "balance_add":
                        print(f"[VOICE] Обрабатываем пополнение баланса для {user_role}")
                        if user_role == "manager":
                            print(f"[VOICE] Вызываем process_balance_add с данными: {parsed_data}")
                            from handlers.manager import process_balance_add
                            await process_balance_add(message, parsed_data)
                        else:
                            await message.answer("❌ Только руководители могут пополнять баланс.")
                            
                    elif operation_type == "balance_reset":
                        print(f"[VOICE] Обрабатываем обнуление баланса для {user_role}")
                        if user_role == "manager":
                            print(f"[VOICE] Вызываем process_balance_reset с данными: {parsed_data}")
                            from handlers.manager import process_balance_reset
                            await process_balance_reset(message, parsed_data)
                        else:
                            await message.answer("❌ Только руководители могут обнулять баланс.")
                            
                    elif operation_type == "payment_request":
                        if user_role == "marketer":
                            await voice_processor._handle_voice_payment_request(message, parsed_data)
                        else:
                            await message.answer("❌ Только маркетологи могут создавать заявки на оплату.")
                            
                    elif operation_type == "payment_confirm":
                        if user_role == "financier":
                            await voice_processor._handle_voice_payment_confirm(message, parsed_data)
                        else:
                            await message.answer("❌ Только финансисты могут подтверждать оплаты.")
                            
                    elif operation_type == "analytics_query":
                        # Простые аналитические запросы доступны всем ролям
                        description = parsed_data.get("description", "").lower()
                        original_text = transcription.lower()
                        
                        # Проверяем тип запроса
                        if any(word in description for word in ['баланс', 'balance']) or \
                           any(word in original_text for word in ['баланс', 'balance', 'сколько денег', 'показать баланс', 'покажи баланс', 'какой баланс', 'текущий баланс']):
                            print(f"[VOICE] Обрабатываем запрос баланса для {user_role}")
                            print(f"[VOICE] Description: '{description}', Original: '{original_text}'")
                            if user_role == "manager":
                                print(f"[VOICE] Вызываем statistics_handler для manager")
                                from handlers.manager import statistics_handler
                                await statistics_handler(message)
                            elif user_role == "financier":
                                print(f"[VOICE] Вызываем balance_command_handler для financier")
                                from handlers.financier import balance_command_handler
                                await balance_command_handler(message)
                            else:
                                await message.answer("❌ Просмотр баланса доступен только финансистам и руководителям.")
                        elif any(word in description for word in ['статистика', 'статус']) or \
                             any(word in original_text for word in ['статистика', 'статс', 'показать статистику']):
                            if user_role == "manager":
                                from handlers.manager import statistics_handler
                                await statistics_handler(message)
                            else:
                                await message.answer("❌ Статистика доступна только руководителям.")
                        elif any(word in description for word in ['операции', 'история']) or \
                             any(word in original_text for word in ['операции', 'история', 'мои операции', 'последние операции']):
                            print(f"[VOICE] Обрабатываем операции/историю для {user_role}")
                            print(f"[VOICE] Description: '{description}', Original: '{original_text}'")
                            if user_role == "manager":
                                print(f"[VOICE] Направляем менеджера в AI Assistant для операций")
                                # Для менеджеров - направляем в AI Assistant для полной аналитики
                                await voice_processor._handle_voice_ai_analytics(message, parsed_data, transcription)
                            elif user_role == "financier":
                                print(f"[VOICE] Вызываем operations_handler для financier")
                                from handlers.financier import operations_handler
                                await operations_handler(message)
                            elif user_role == "marketer":
                                print(f"[VOICE] Вызываем my_payments_handler для marketer")
                                from handlers.marketer import my_payments_handler
                                await my_payments_handler(message)
                            else:
                                print(f"[VOICE] Неизвестная роль для операций: {user_role}")
                                await message.answer("❌ История операций доступна только авторизованным пользователям.")
                        elif any(word in description for word in ['заявки', 'платежи']) or \
                             any(word in original_text for word in ['заявки', 'мои заявки', 'статус заявок', 'последние заявки']):
                            if user_role == "marketer":
                                # Проверяем, что запрашивается - одна последняя или все заявки
                                if any(word in original_text for word in ['последн', 'самой последней', 'крайней']):
                                    from handlers.marketer import last_payment_handler
                                    await last_payment_handler(message)
                                else:
                                    from handlers.marketer import my_payments_handler
                                    await my_payments_handler(message)
                            else:
                                await message.answer("❌ Просмотр заявок доступен только маркетологам.")
                        elif any(word in description for word in ['сводка', 'отчет за день']) or \
                             any(word in original_text for word in ['сводка', 'отчет за день', 'что сегодня']):
                            if user_role == "manager":
                                from handlers.manager import summary_handler
                                await summary_handler(message)
                            else:
                                await message.answer("❌ Сводка за день доступна только руководителям.")
                        else:
                            # Общий случай - показываем что доступно для роли
                            if user_role == "manager":
                                from handlers.manager import statistics_handler
                                await statistics_handler(message)
                            elif user_role == "financier":
                                from handlers.financier import balance_command_handler
                                await balance_command_handler(message)
                            elif user_role == "marketer":
                                from handlers.marketer import my_payments_handler
                                await my_payments_handler(message)
                            else:
                                await message.answer("❌ Аналитические запросы доступны только авторизованным пользователям.")
                            
                    elif operation_type == "ai_analytics":
                        # Сложные аналитические запросы через AI-помощника (только для руководителей)
                        if user_role == "manager":
                            await voice_processor._handle_voice_ai_analytics(message, parsed_data, transcription)
                        elif user_role == "marketer":
                            # Для маркетологов показываем их заявки
                            original_text = transcription.lower()
                            if any(word in original_text for word in ['статус', 'заявк', 'последн', 'мои заявки', 'заявки']):
                                # Проверяем, что запрашивается - одна последняя или все заявки
                                if any(word in original_text for word in ['последн', 'самой последней', 'крайней']):
                                    from handlers.marketer import last_payment_handler
                                    await last_payment_handler(message)
                                else:
                                    from handlers.marketer import my_payments_handler
                                    await my_payments_handler(message)
                            else:
                                await message.answer("❌ AI-аналитика доступна только руководителям.")
                        else:
                            await message.answer("❌ AI-аналитика доступна только руководителям.")
                            
                    elif operation_type == "system_command":
                        # Системные команды (помощь, старт, дашборд, AI и т.д.)
                        description = parsed_data.get("description", "").lower()
                        original_text = transcription.lower()
                        
                        # Проверяем и в описании, и в оригинальном тексте
                        if any(word in description for word in ['помощь', 'справка', 'help']) or \
                           any(word in original_text for word in ['помощь', 'справка', 'help', 'что умеешь', 'что ты умеешь', 'возможности']):
                            from handlers.common import help_handler
                            await help_handler(message)
                        elif any(word in description for word in ['старт', 'начать', 'привет', 'start', 'меню', 'menu']) or \
                             any(word in original_text for word in ['старт', 'начать', 'привет', 'start', 'меню', 'menu', 'здравствуй']):
                            from handlers.common import start_handler
                            await start_handler(message)
                        elif any(word in description for word in ['дашборд', 'dashboard', 'ссылка', 'веб-интерфейс', 'панель']) or \
                             any(word in original_text for word in ['дашборд', 'dashboard', 'ссылка', 'веб-интерфейс', 'панель']):
                            if user_role == "manager":
                                from handlers.manager import dashboard_command_handler
                                await dashboard_command_handler(message)
                            else:
                                await message.answer("❌ Доступ к дашборду есть только у руководителей.")
                        elif any(word in description for word in ['ии', 'ai', 'помощник', 'аналитик', 'искусственный']) or \
                             any(word in original_text for word in ['ии', 'ai', 'помощник', 'аналитик', 'искусственный']):
                            await voice_processor._handle_voice_ai_help(message, user_role)
                        elif any(word in description for word in ['примеры', 'example']) or \
                             any(word in original_text for word in ['примеры', 'покажи примеры', 'как создать заявку', 'примеры заявок']):
                            if user_role == "marketer":
                                from handlers.marketer import examples_handler
                                await examples_handler(message)
                            else:
                                await message.answer("❌ Примеры заявок доступны только маркетологам.")
                        elif any(word in description for word in ['формат', 'format']) or \
                             any(word in original_text for word in ['формат', 'поддерживаемые форматы', 'какие форматы']):
                            if user_role == "marketer":
                                from handlers.marketer import formats_handler
                                await formats_handler(message)
                            else:
                                await message.answer("❌ Форматы заявок доступны только маркетологам.")
                        elif any(word in description for word in ['естественный язык', 'natural']) or \
                             any(word in original_text for word in ['естественный язык', 'как говорить', 'примеры речи']):
                            if user_role == "marketer":
                                from handlers.marketer import natural_handler
                                await natural_handler(message)
                            else:
                                await message.answer("❌ Примеры естественного языка доступны только маркетологам.")
                        elif any(word in description for word in ['отчет', 'report', 'сводка']) or \
                             any(word in original_text for word in ['отчет', 'отчеты', 'сводка', 'summary']):
                            if user_role == "manager":
                                from handlers.manager import reports_handler
                                await reports_handler(message)
                            else:
                                await message.answer("❌ Отчеты доступны только руководителям.")
                        else:
                            # Если не удалось определить конкретную команду, пробуем помощь по умолчанию
                            logger.info(f"Неопределенная системная команда: '{original_text}', описание: '{description}'")
                            from handlers.common import help_handler
                            await help_handler(message)
                            
                    else:
                        logger.info(f"Неизвестная операция: {operation_type}")
                        await message.answer(
                            f"🤖 Распознано: '{transcription}'\n"
                            f"Тип операции: {operation_type}\n\n"
                            f"Не знаю, как обработать эту операцию. Попробуйте переформулировать."
                        )
                        
                else:
                    logger.info("ИИ-агент не смог определить тип операции")
                    # Показываем подсказки в зависимости от роли
                    suggestions = voice_processor._get_voice_suggestions_for_role(user_role)
                    await message.answer(
                        f"🤖 Распознано: '{transcription}'\n\n"
                        f"Не понял, что нужно сделать. Возможные команды для вашей роли:\n\n"
                        f"{suggestions}\n\n"
                        f"Попробуйте переформулировать или напишите текстом."
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке через ИИ-агент: {e}")
                await message.reply(f"⚠️ Распознано: {transcription}\n"
                                  f"Произошла ошибка при анализе: {str(e)}")
                                  
            
        else:
            print(f"[VOICE ERROR] Не удалось распознать голосовое сообщение от пользователя {user_id}")
            logger.warning(f"Не удалось распознать голосовое сообщение от пользователя {user_id}")
            await message.reply("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз.")
    
    except Exception as e:
        print(f"[VOICE ERROR] Общая ошибка в handle_voice_message: {e}")
        logger.error(f"Общая ошибка в handle_voice_message: {e}")
        await message.reply("❌ Произошла ошибка при обработке голосового сообщения.")

def setup_voice_handlers(dp):
    dp.include_router(router)