import os
import tempfile
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, Voice
import openai

from utils.config import Config
import logging

logger = logging.getLogger(__name__)
router = Router()

class VoiceProcessor:
    def __init__(self):
        self.config = Config()
        openai.api_key = self.config.OPENAI_API_KEY
        
    async def process_voice_message(self, voice: Voice, bot) -> Optional[str]:
        try:
            voice_file = await bot.get_file(voice.file_id)
            
            with tempfile.NamedTemporaryFile(suffix='.oga', delete=False) as temp_file:
                await bot.download_file(voice_file.file_path, temp_file)
                temp_file_path = temp_file.name
            
            with open(temp_file_path, 'rb') as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"
                )
            
            os.unlink(temp_file_path)
            
            return transcript.text
            
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового сообщения: {e}")
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
                    f"❌ **Недостаточно средств на балансе!**\n\n"
                    f"💰 Текущий баланс: **{current_balance:.2f}$**\n"
                    f"💸 Запрашиваемая сумма: **{amount:.2f}$**\n"
                    f"📉 Нехватка: **{amount - current_balance:.2f}$**\n\n"
                    f"Обратитесь к руководителю для пополнения баланса.",
                    parse_mode="Markdown"
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
                f"✅ **Заявка создана!**\n\n"
                f"🆔 ID заявки: **{payment_id}**\n"
                f"💰 Сумма: **{amount}$**\n"
                f"📱 Платформа: **{platform}**\n"
                f"📋 Проект: **{project}**\n"
                f"💳 Способ оплаты: **{payment_method}**\n"
                f"📝 Описание: {description}\n\n"
                f"📤 Финансистам отправлено уведомление для обработки.",
                parse_mode="Markdown"
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
                    f"❌ Заявка с ID `{payment_id}` не найдена.",
                    parse_mode="Markdown"
                )
                return
            
            if payment["status"] != "pending":
                await message.answer(
                    f"❌ Заявка `{payment_id}` уже обработана.\n"
                    f"Текущий статус: **{payment['status']}**",
                    parse_mode="Markdown"
                )
                return
            
            # Списание средств с баланса
            current_balance = await BalanceDB.get_balance()
            payment_amount = float(payment["amount"])
            
            if current_balance < payment_amount:
                await message.answer(
                    f"❌ **Недостаточно средств для подтверждения!**\n\n"
                    f"💰 Текущий баланс: **{current_balance:.2f}$**\n"
                    f"💸 Сумма заявки: **{payment_amount:.2f}$**\n"
                    f"📉 Нехватка: **{payment_amount - current_balance:.2f}$**",
                    parse_mode="Markdown"
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
                f"✅ **Оплата подтверждена!**\n\n"
                f"🆔 ID заявки: **{payment_id}**\n"
                f"💰 Сумма: **{payment_amount:.2f}$**\n"
                f"📱 Платформа: **{payment['platform']}**\n"
                f"📋 Проект: **{payment['project']}**\n"
                f"💳 Способ: **{payment['payment_method']}**\n\n"
                f"💰 Баланс: **{current_balance:.2f}$** → **{new_balance:.2f}$**\n"
                f"📤 Маркетологу отправлено уведомление.",
                parse_mode="Markdown"
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
            
            # Отправляем запрос в AI-помощник менеджера
            from nlp.manager_ai_assistant import process_manager_query
            
            # Уведомляем пользователя о начале обработки
            await message.answer("🤖 Анализирую данные, момент...")
            
            response = await process_manager_query(query)
            
            # Отправляем ответ пользователя
            await message.answer(
                f"🤖 **AI-Аналитик:**\n\n{response}",
                parse_mode="Markdown"
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
                "🤖 **AI-Помощник активирован!**\n\n"
                "**Примеры голосовых запросов:**\n"
                "• 'Сколько человек в команде?'\n"
                "• 'Какой сейчас баланс?'\n"
                "• 'Платежи за неделю'\n"
                "• 'Покажи ожидающие оплаты'\n"
                "• 'Последние операции'\n"
                "• 'История баланса'\n"
                "• 'Статистика по платформам'\n\n"
                "**Или используйте текстовую команду:**\n"
                "• `/ai Ваш вопрос`\n\n"
                "Просто задайте голосовой вопрос!",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ AI-помощник доступен только руководителям.")

    def _get_voice_suggestions_for_role(self, user_role: str) -> str:
        """Возвращает подсказки голосовых команд для конкретной роли"""
        suggestions = {
            "manager": [
                "👨‍💼 **Руководитель:**",
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
                "💰 **Финансист:**",
                "• 'Оплачено 123' - подтверждение оплаты заявки",
                "• 'Покажи баланс' - текущий баланс системы",
                "• 'Последние операции' - история платежей",
                "• 'Помощь' - справочная информация"
            ],
            "marketer": [
                "📱 **Маркетолог:**",
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
        logger.info(f"Получено голосовое сообщение от пользователя {user_id}")
        
        transcription = await voice_processor.process_voice_message(message.voice, message.bot)
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
                        if user_role == "manager":
                            from handlers.manager import process_balance_add
                            await process_balance_add(message, parsed_data)
                        else:
                            await message.answer("❌ Только руководители могут пополнять баланс.")
                            
                    elif operation_type == "balance_reset":
                        if user_role == "manager":
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
                        if user_role == "manager":
                            from handlers.manager import statistics_handler
                            await statistics_handler(message)
                        elif user_role == "financier":
                            from handlers.financier import balance_command_handler
                            await balance_command_handler(message)
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
                                await message.answer("📊 Маркетологи могут просматривать только свои заявки.\nДля получения статистики обратитесь к руководителю.")
                            
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
            logger.warning(f"Не удалось распознать голосовое сообщение от пользователя {user_id}")
            await message.reply("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз.")
    
    except Exception as e:
        logger.error(f"Общая ошибка в handle_voice_message: {e}")
        await message.reply("❌ Произошла ошибка при обработке голосового сообщения.")

def setup_voice_handlers(dp):
    dp.include_router(router)