"""
Обработчики для руководителей.
Обрабатывает пополнение баланса и команды управления.
"""

import re
from datetime import datetime
from typing import Dict, Any
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.config import Config
from utils.logger import log_action
from db.database import BalanceDB, PaymentDB
from nlp.universal_ai_parser import UniversalAIParser
from nlp.manager_ai_assistant import process_manager_query
from handlers.nlp_command_handler import smart_message_router
import logging

logger = logging.getLogger(__name__)


async def is_analytics_query(text: str) -> bool:
    """Определяет, является ли текст аналитическим запросом"""
    # Ключевые слова для аналитических запросов
    analytics_keywords = [
        'сколько', 'какой', 'какие', 'как', 'что', 'где', 'когда',
        'баланс', 'платежи', 'команда', 'проекты', 'статистика',
        'операции', 'история', 'неделя', 'сегодня', 'вчера',
        'ожидающие', 'оплата', 'человек', 'размер', 'состояние',
        'динамика', 'изменения', 'активность', 'отчет', 'данные'
    ]
    
    # Исключаем явные команды пополнения баланса
    balance_keywords = [
        'пополн', 'добав', 'закин', 'внес', 'поступ', 'added',
        'зачисл', 'transfer', 'plus', 'плюс', '+', 'увелич'
    ]
    
    text_lower = text.lower()
    
    # Если есть ключевые слова пополнения баланса и цифры, то это не аналитический запрос
    has_balance_keywords = any(keyword in text_lower for keyword in balance_keywords)
    has_numbers = re.search(r'\d', text)
    
    if has_balance_keywords and has_numbers:
        return False
    
    # Если есть аналитические ключевые слова, то это аналитический запрос
    has_analytics_keywords = any(keyword in text_lower for keyword in analytics_keywords)
    
    # Проверяем на вопросительные конструкции
    is_question = text.strip().endswith('?') or any(word in text_lower for word in ['сколько', 'какой', 'какие', 'как', 'что', 'где', 'когда'])
    
    return has_analytics_keywords or is_question


async def is_reset_balance_query(text: str) -> bool:
    """Определяет, является ли текст командой обнуления баланса"""
    reset_patterns = [
        r'обнул[и|ить|ять]?\s+баланс',
        r'очист[и|ить|ять]?\s+баланс',
        r'баланс\s+(?:в\s+)?0(?:\.0+)?(?:\s*\$)?(?:\s+|$)',  # Более точный паттерн для "баланс 0"
        r'сдела[й|ть]?\s+нулевой\s+баланс',
        r'обнулить?\s+баланс',
        r'обнули\s+баланс',
        r'очисти\s+баланс',
        r'баланс\s+ноль',
        r'баланс\s+на\s+ноль',
        r'сброс\s+баланса',
        r'сбрось?\s+баланс',
        r'reset\s+balance',
        r'clear\s+balance',
        r'balance\s+0(?:\.0+)?(?:\s*\$)?(?:\s+|$)',  # Более точный паттерн для "balance 0"
        r'balance\s+zero'
    ]
    
    text_lower = text.lower()
    
    # Исключаем сообщения, которые явно содержат команды пополнения
    exclude_patterns = [
        r'пополн[и|ить|ять]',
        r'добав[и|ить|ять]',
        r'закин[у|ь|уть]',
        r'внес[и|ти]',
        r'поступ[и|ить|ление]',
        r'added',
        r'зачисл[и|ить|ять]',
        r'transfer'
    ]
    
    # Если есть ключевые слова пополнения, не считаем это обнулением
    for exclude_pattern in exclude_patterns:
        if re.search(exclude_pattern, text_lower):
            return False
    
    for pattern in reset_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False


async def analytics_query_handler(message: Message):
    """Обработчик аналитических запросов через AI"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        return
    
    log_action(user_id, "analytics_query", message.text)
    
    try:
        # Отправляем запрос в AI-помощник
        response = await process_manager_query(message.text)
        
        # Отправляем ответ пользователю
        await message.answer(
            f"🤖 **AI-Аналитика:**\n\n{response}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка AI-помощника: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте переформулировать вопрос или обратитесь к администратору."
        )


async def reset_balance_handler(message: Message):
    """Обработчик команды обнуления баланса"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        return
    
    log_action(user_id, "reset_balance_attempt", message.text)
    
    try:
        # Получаем текущий баланс для логирования
        current_balance = await BalanceDB.get_balance()
        
        # Обнуляем баланс (устанавливаем в 0)
        await reset_balance_to_zero()
        
        # Отправляем подтверждение
        await message.answer(
            f"⚠️ БАЛАНС ОБНУЛЕН\n\n"
            f"📊 Было: {current_balance:.2f}$\n"
            f"🔄 Стало: 0.00$\n"
            f"👤 Выполнил: {message.from_user.username or 'Unknown'}\n\n"
            f"✅ Операция завершена успешно"
        )
        
        # Уведомляем финансистов об обнулении
        await notify_financiers_balance_reset(
            message.bot,
            current_balance,
            message.from_user.username or "Unknown"
        )
        
        log_action(user_id, "reset_balance_success", f"Баланс обнулен с {current_balance:.2f}$")
        
    except Exception as e:
        logger.error(f"Ошибка обнуления баланса: {e}")
        await message.answer(
            "❌ Произошла ошибка при обнулении баланса.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


async def reset_balance_to_zero():
    """Обнуляет баланс в базе данных"""
    config = Config()
    
    # Получаем текущий баланс
    current_balance = await BalanceDB.get_balance()
    
    # Если баланс уже 0, ничего не делаем
    if current_balance == 0:
        return
    
    # Вычисляем сумму для списания
    amount_to_subtract = current_balance
    
    # Списываем весь баланс
    await BalanceDB.subtract_balance(
        amount_to_subtract,
        payment_id=0,  # Специальный ID для обнуления
        description="Обнуление баланса руководителем"
    )


async def notify_financiers_balance_reset(bot, old_balance: float, username: str):
    """Уведомление финансистов об обнулении баланса"""
    config = Config()
    
    notification_text = (
        f"⚠️ БАЛАНС ОБНУЛЕН\n\n"
        f"📊 Было: {old_balance:.2f}$\n"
        f"🔄 Стало: 0.00$\n"
        f"👤 Выполнил: {username}\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    for financier_id in config.FINANCIERS:
        try:
            await bot.send_message(
                financier_id,
                notification_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об обнулении финансисту {financier_id}: {e}")


async def add_balance_handler(message: Message):
    """Обработчик всех сообщений от руководителей с приоритетом на AI"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        return
    
    # Сначала проверяем, не является ли это командой
    if await smart_message_router(message):
        return  # Сообщение обработано как команда
    
    log_action(user_id, "message_processing", message.text)
    
    try:
        # Используем AI для понимания сообщения
        ai_parser = UniversalAIParser()
        parsed_data = await ai_parser.parse_message(message.text, "manager")
        
        if not parsed_data:
            await handle_unparseable_message(message)
            return
        
        # Обрабатываем в зависимости от типа операции
        operation_type = parsed_data["operation_type"]
        confidence = parsed_data.get("confidence", 0)
        
        # Если уверенность низкая, предлагаем уточнение
        if confidence < 0.7:
            await handle_low_confidence_message(message, parsed_data)
            return
        
        # Маршрутизация по типу операции
        if operation_type == "balance_add":
            await process_balance_add(message, parsed_data)
        elif operation_type == "balance_reset":
            await process_balance_reset(message, parsed_data)
        elif operation_type == "analytics_query":
            await process_analytics_query(message, parsed_data)
        elif operation_type == "system_command":
            await process_system_command(message, parsed_data)
        else:
            await handle_unknown_operation(message, parsed_data)
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await handle_processing_error(message, e)


async def process_balance_add(message: Message, parsed_data: Dict[str, Any]):
    """Обработка пополнения баланса через AI"""
    user_id = message.from_user.id
    amount = parsed_data.get("amount")
    description = parsed_data.get("description", "пополнение баланса")
    
    if not amount or amount <= 0:
        await message.answer(
            "❌ Не удалось определить корректную сумму пополнения.\n"
            "Попробуйте указать сумму более явно.",
            parse_mode="Markdown"
        )
        return
    
    try:
        # Получение текущего баланса
        old_balance = await BalanceDB.get_balance()
        
        # Пополнение баланса
        await BalanceDB.add_balance(amount, user_id, description)
        
        # Получение нового баланса
        new_balance = await BalanceDB.get_balance()
        
        # Формируем детальное описание
        details = []
        if parsed_data.get("platform"):
            details.append(f"🎯 **Платформа:** {parsed_data['platform']}")
        if parsed_data.get("project"):
            details.append(f"📂 **Проект:** {parsed_data['project']}")
        if parsed_data.get("payment_method"):
            details.append(f"💳 **Способ оплаты:** {parsed_data['payment_method']}")
        if parsed_data.get("payment_details"):
            details.append(f"🔢 **Детали:** {parsed_data['payment_details']}")
        
        details_text = "\n".join(details) if details else ""
        
        # Отправка подтверждения
        await message.answer(
            f"✅ **БАЛАНС ПОПОЛНЕН!**\n\n"
            f"💰 **Сумма пополнения:** {amount:.2f}$\n"
            f"📊 **Было:** {old_balance:.2f}$\n"
            f"📈 **Стало:** {new_balance:.2f}$\n"
            f"📝 **Описание:** {description}\n"
            f"{details_text}\n\n"
            f"✅ Баланс успешно обновлен!",
            parse_mode="Markdown"
        )
        
        # Уведомление финансистов о пополнении
        await notify_financiers_balance_updated(
            message.bot, 
            amount, 
            new_balance, 
            description
        )
        
        log_action(user_id, "balance_add_success", f"Добавлено {amount}$ - {description}")
        
    except Exception as e:
        logger.error(f"Ошибка пополнения баланса: {e}")
        await message.answer(
            "❌ Произошла ошибка при пополнении баланса.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


async def process_balance_reset(message: Message, parsed_data: Dict[str, Any]):
    """Обработка обнуления баланса через AI"""
    await reset_balance_handler(message)


async def process_analytics_query(message: Message, parsed_data: Dict[str, Any]):
    """Обработка аналитических запросов через AI"""
    await analytics_query_handler(message)


async def process_system_command(message: Message, parsed_data: Dict[str, Any]):
    """Обработка системных команд через AI"""
    # Можно добавить логику для системных команд
    await message.answer("🤖 Системная команда распознана, но пока не реализована.")


async def handle_unparseable_message(message: Message):
    """Обработка сообщений, которые AI не смог распарсить"""
    await message.answer(
        "❌ **Не удалось распознать команду.**\n\n"
        "🤖 **AI-помощник поддерживает:**\n"
        "• Пополнение баланса\n"
        "• Обнуление баланса\n"
        "• Аналитические запросы\n"
        "• Системные команды\n\n"
        "**Примеры:**\n"
        "• `пополни баланс на 500 баксов для Инсты`\n"
        "• `обнули баланс`\n"
        "• `какой сейчас баланс?`\n"
        "• `сколько потратили на рекламу?`",
        parse_mode="Markdown"
    )


async def handle_low_confidence_message(message: Message, parsed_data: Dict[str, Any]):
    """Обработка сообщений с низкой уверенностью AI"""
    operation_type = parsed_data["operation_type"]
    confidence = parsed_data.get("confidence", 0)
    
    await message.answer(
        f"🤔 **Не уверен в интерпретации сообщения**\n\n"
        f"🤖 **AI определил:** {operation_type}\n"
        f"📊 **Уверенность:** {confidence:.1%}\n\n"
        f"Пожалуйста, переформулируйте сообщение более четко.\n\n"
        f"**Примеры четких команд:**\n"
        f"• `пополни баланс на 500 долларов`\n"
        f"• `обнули баланс полностью`\n"
        f"• `какой текущий баланс?`",
        parse_mode="Markdown"
    )


async def handle_unknown_operation(message: Message, parsed_data: Dict[str, Any]):
    """Обработка неизвестных операций"""
    await message.answer(
        "❓ **Неизвестная операция**\n\n"
        "🤖 AI не смог определить тип операции.\n"
        "Попробуйте переформулировать сообщение или используйте команды:\n\n"
        "• `/balance` - текущий баланс\n"
        "• `/stats` - статистика\n"
        "• `/ai вопрос` - прямое обращение к AI\n"
        "• `/help` - помощь",
        parse_mode="Markdown"
    )


async def handle_processing_error(message: Message, error: Exception):
    """Обработка ошибок при обработке сообщения"""
    await message.answer(
        "❌ **Произошла ошибка при обработке сообщения**\n\n"
        "🤖 AI-помощник временно недоступен.\n"
        "Попробуйте еще раз или обратитесь к администратору.\n\n"
        "**Альтернативные команды:**\n"
        "• `/balance` - текущий баланс\n"
        "• `/stats` - статистика\n"
        "• `/help` - помощь",
        parse_mode="Markdown"
    )


async def statistics_handler(message: Message):
    """Обработчик команды статистики (только для руководителей)"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        await message.answer("❌ У вас нет доступа к статистике.")
        return
    
    log_action(user_id, "statistics_request", "")
    
    try:
        # Получение статистики из базы данных
        current_balance = await BalanceDB.get_balance()
        pending_payments = await PaymentDB.get_pending_payments()
        
        # Подсчет сумм ожидающих платежей
        total_pending = sum(payment["amount"] for payment in pending_payments)
        
        status_emoji = "✅" if current_balance >= config.LOW_BALANCE_THRESHOLD else "⚠️"
        
        await message.answer(
            f"📊 **СТАТИСТИКА СИСТЕМЫ**\n\n"
            f"{status_emoji} **Баланс:** {current_balance:.2f}$\n"
            f"⏳ **Ожидающих оплат:** {len(pending_payments)} шт.\n"
            f"💸 **Сумма ожидающих:** {total_pending:.2f}$\n"
            f"📉 **Порог уведомлений:** {config.LOW_BALANCE_THRESHOLD}$\n\n"
            f"{'🟢 Система работает нормально' if current_balance >= config.LOW_BALANCE_THRESHOLD else '🔴 Требуется внимание к балансу'}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.answer(
            "❌ Произошла ошибка при получении статистики."
        )


async def notify_financiers_balance_updated(bot, amount: float, new_balance: float, description: str):
    """Уведомление финансистов об обновлении баланса"""
    config = Config()
    
    notification_text = (
        f"💰 **БАЛАНС ПОПОЛНЕН**\n\n"
        f"📈 **Пополнение:** +{amount:.2f}$\n"
        f"💰 **Новый баланс:** {new_balance:.2f}$\n"
        f"📝 **Описание:** {description if description else 'Пополнение баланса'}"
    )
    
    for financier_id in config.FINANCIERS:
        try:
            await bot.send_message(
                financier_id,
                notification_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление финансисту {financier_id}: {e}")


async def ai_assistant_handler(message: Message):
    """Обработчик команды /ai - прямое обращение к AI-помощнику"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        await message.answer("❌ У вас нет доступа к AI-помощнику.")
        return
    
    # Извлекаем вопрос после команды
    query = message.text.replace('/ai', '').strip()
    
    if not query:
        await message.answer(
            "🤖 **AI-Помощник активирован!**\n\n"
            "**Примеры запросов:**\n"
            "• `/ai Сколько человек в команде?`\n"
            "• `/ai Какой сейчас баланс?`\n"
            "• `/ai Платежи за неделю`\n"
            "• `/ai Покажи ожидающие оплаты`\n"
            "• `/ai Последние операции`\n"
            "• `/ai История баланса`\n\n"
            "**Или просто задайте вопрос:**\n"
            "• `Сколько человек в команде?`\n"
            "• `Какие платежи были сегодня?`\n"
            "• `Скажи, какой сейчас баланс?`",
            parse_mode="Markdown"
        )
        return
    
    log_action(user_id, "ai_query", query)
    
    try:
        # Отправляем запрос в AI-помощник
        response = await process_manager_query(query)
        
        # Отправляем ответ пользователю
        await message.answer(
            f"🤖 **AI-Помощник:**\n\n{response}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка AI-помощника: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте переформулировать вопрос или обратитесь к администратору."
        )


async def reset_balance_command_handler(message: Message):
    """Обработчик команды /resetbalance"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await reset_balance_handler(message)


async def dashboard_command_handler(message: Message):
    """Обработчик команды /dashboard"""
    user_id = message.from_user.id
    config = Config()
    
    # Проверка роли
    if config.get_user_role(user_id) != "manager":
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    dashboard_url = "http://127.0.0.1:8000?token=demo_token"
    
    await message.answer(
        f"📊 Веб-дашборд для аналитики\n\n"
        f"🔗 <a href=\"{dashboard_url}\">Открыть дашборд</a>\n\n"
        f"🔑 Токен авторизации: demo_token\n\n"
        f"ℹ️ Дашборд содержит:\n"
        f"• Текущий баланс и статистика\n"
        f"• История транзакций\n"
        f"• Графики и аналитика\n"
        f"• Управление системой\n\n"
        f"⚠️ Убедитесь, что дашборд запущен командой:\n"
        f"python start_dashboard.py\n\n"
        f"📋 Прямая ссылка:\n{dashboard_url}",
        parse_mode="HTML"
    )


def setup_manager_handlers(dp: Dispatcher):
    """Регистрация обработчиков для руководителей"""
    
    def is_manager(message: Message) -> bool:
        return Config.get_user_role(message.from_user.id) == "manager"
    
    # Обработчик пополнения баланса (все текстовые сообщения от руководителей, кроме команд)
    dp.message.register(
        add_balance_handler,
        F.text & (~F.text.regexp(r"^/", flags=re.IGNORECASE)),  # не команды
        is_manager
    )
    
    # Команда статистики
    dp.message.register(
        statistics_handler,
        Command("stats"),
        is_manager
    )
    
    # Команда баланса для руководителей
    dp.message.register(
        statistics_handler,  # Используем ту же функцию, что и для статистики
        Command("balance"),
        is_manager
    )
    
    # Команда AI-помощника
    dp.message.register(
        ai_assistant_handler,
        Command("ai"),
        is_manager
    )
    
    # Команда обнуления баланса
    dp.message.register(
        reset_balance_command_handler,
        Command("resetbalance"),
        is_manager
    )
    
    # Команда веб-дашборда
    dp.message.register(
        dashboard_command_handler,
        Command("dashboard"),
        is_manager
    ) 