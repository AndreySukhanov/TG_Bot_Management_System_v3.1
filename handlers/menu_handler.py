"""
Обработчик интерактивных меню и кнопок.
Обрабатывает нажатия на кнопки меню для всех ролей.
"""

import logging
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from utils.config import Config
from utils.logger import log_action
# from utils.keyboards import get_main_menu_keyboard, get_examples_keyboard, get_quick_actions_keyboard

logger = logging.getLogger(__name__)


async def menu_button_handler(message: Message):
    """Обработчик нажатий на кнопки меню"""
    user_id = message.from_user.id
    config = Config()
    user_role = config.get_user_role(user_id)
    
    if user_role == "unknown":
        return
    
    button_text = message.text
    log_action(user_id, "menu_button", button_text)
    
    try:
        # Обработка общих кнопок
        if button_text == "🏠 Главное меню":
            await show_main_menu(message, user_role)
            
        elif button_text == "📋 Справка":
            from handlers.common import help_handler
            await help_handler(message)
            
        # Обработка кнопок маркетологов
        elif user_role == "marketer":
            if button_text == "💳 Создать заявку на оплату":
                await message.answer(
                    "💳 <b>Создание заявки на оплату</b>\n\n"
                    "🆕 <b>Поддерживается естественный язык!</b>\n\n"
                    "<b>Примеры:</b>\n"
                    "• <code>Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту</code>\n"
                    "• <code>Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890</code>\n"
                    "• <code>Оплати инстаграм 200$ проект Гамма счет 1234-5678</code>\n\n"
                    "Просто напишите свой запрос естественным языком!",
                    parse_mode="HTML"
                )
                
            elif button_text == "📝 Примеры заявок":
                await message.answer(
                    "📝 <b>Примеры заявок на оплату:</b>\n\n"
                    "<b>1. Классический формат:</b>\n"
                    "<code>Нужна оплата сервиса [НАЗВАНИЕ] на сумму [СУММА]$ для проекта [ПРОЕКТ], [СПОСОБ]: [ДЕТАЛИ]</code>\n\n"
                    "<b>2. Естественный язык:</b>\n"
                    "• <code>Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту</code>\n"
                    "• <code>Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890</code>\n"
                    "• <code>Оплати инстаграм 200$ проект Гамма счет 1234-5678</code>\n\n"
                    "<b>Способы оплаты:</b>\n"
                    "• <b>crypto</b> - криптовалята\n"
                    "• <b>phone</b> - номер телефона\n"
                    "• <b>account</b> - банковский счет\n"
                    "• <b>file</b> - файл с реквизитами",
                    parse_mode="HTML"
                )
        
        # Обработка кнопок финансистов
        elif user_role == "financier":
            if button_text == "💰 Показать баланс":
                from handlers.financier import balance_command_handler
                await balance_command_handler(message)
                
            elif button_text == "✅ Подтвердить оплату":
                await message.answer(
                    "✅ <b>Подтверждение оплаты</b>\n\n"
                    "<b>Формат:</b>\n"
                    "<code>Оплачено [ID_ЗАЯВКИ]</code> + прикрепите подтверждение\n\n"
                    "<b>Примеры:</b>\n"
                    "• <code>Оплачено 123</code> + скриншот\n"
                    "• <code>Оплачено 124, хэш: 0xabc123...</code>\n\n"
                    "Отправьте ID заявки и прикрепите файл подтверждения.",
                    parse_mode="HTML"
                )
                
            elif button_text == "📊 Мои операции":
                await message.answer(
                    "📊 <b>Мои операции</b>\n\n"
                    "Функция в разработке...\n"
                    "Скоро вы сможете посмотреть историю своих операций.",
                    parse_mode="HTML"
                )
        
        # Обработка кнопок руководителей
        elif user_role == "manager":
            if button_text == "💰 Показать баланс":
                from handlers.manager import statistics_handler
                await statistics_handler(message)
                
            elif button_text == "📊 Статистика":
                from handlers.manager import statistics_handler
                await statistics_handler(message)
                
            elif button_text == "💵 Пополнить баланс":
                await message.answer(
                    "💵 <b>Пополнение баланса</b>\n\n"
                    "🆕 <b>Поддерживается естественный язык!</b>\n\n"
                    "<b>Примеры:</b>\n"
                    "• <code>Пополнение 1000</code>\n"
                    "• <code>Добавить 500 на баланс</code>\n"
                    "• <code>Закинь 200 долларов от клиента Альфа</code>\n"
                    "• <code>Получили оплату 850$ от заказчика</code>\n\n"
                    "Просто напишите сумму и описание!",
                    parse_mode="HTML"
                )
                
            elif button_text == "📈 Отчеты":
                await message.answer(
                    "📈 <b>Отчеты</b>\n\n"
                    "Функция в разработке...\n\n"
                    "Планируемые отчеты:\n"
                    "• 📊 Статистика по проектам\n"
                    "• 💰 Движение средств\n"
                    "• 📈 Динамика расходов\n"
                    "• 👥 Активность пользователей\n"
                    "• 📅 Отчеты по периодам\n"
                    "• 📤 Экспорт данных",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        logger.error(f"Ошибка обработки кнопки меню: {e}")
        await message.answer("❌ Произошла ошибка при обработке команды.")


async def show_main_menu(message: Message, user_role: str):
    """Показывает главное меню для роли"""
    role_names = {
        "marketer": "Маркетолог",
        "financier": "Финансист", 
        "manager": "Руководитель"
    }
    
    role_descriptions = {
        "marketer": "📝 Создавайте заявки на оплату в естественном языке",
        "financier": "💰 Управляйте балансом и подтверждайте оплаты",
        "manager": "📊 Контролируйте финансы и статистику системы"
    }
    
    await message.answer(
        f"🏠 <b>Главное меню - {role_names[user_role]}</b>\n\n"
        f"{role_descriptions[user_role]}\n\n"
        f"Используйте команды из меню (/) или напишите сообщение:",
        parse_mode="HTML"
    )


async def callback_handler(callback: CallbackQuery):
    """Обработчик callback-запросов от inline кнопок"""
    user_id = callback.from_user.id
    config = Config()
    user_role = config.get_user_role(user_id)
    
    if user_role == "unknown":
        await callback.answer("❌ У вас нет доступа к этому боту.")
        return
    
    callback_data = callback.data
    log_action(user_id, "callback", callback_data)
    
    # Примеры для маркетологов
    if callback_data == "example_crypto":
        await callback.message.answer(
            "💳 <b>Пример заявки с криптовалютой:</b>\n\n"
            "<code>Нужна оплата сервиса Facebook Ads на сумму 100$ для проекта Alpha, криптовалюта: 0x1234567890abcdef</code>\n\n"
            "<b>Или естественным языком:</b>\n"
            "<code>Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_phone":
        await callback.message.answer(
            "📱 <b>Пример заявки с телефоном:</b>\n\n"
            "<code>Оплата сервиса Google Ads на 50$ для проекта Beta, номер телефона: +1234567890</code>\n\n"
            "<b>Или естественным языком:</b>\n"
            "<code>Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_account":
        await callback.message.answer(
            "💰 <b>Пример заявки со счетом:</b>\n\n"
            "<code>Оплата сервиса Instagram на 200$ для проекта Gamma, счет: 1234-5678-9012-3456</code>\n\n"
            "<b>Или естественным языком:</b>\n"
            "<code>Оплати инстаграм 200$ проект Гамма счет 1234-5678</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_file":
        await callback.message.answer(
            "📄 <b>Пример заявки с файлом:</b>\n\n"
            "<code>Нужна оплата сервиса TikTok на 75$ для проекта Delta, счет:</code> + прикрепите файл\n\n"
            "<b>Или естественным языком:</b>\n"
            "<code>Требуется оплата тикток 75$ для проекта Дельта, прикрепляю файл</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_natural":
        await callback.message.answer(
            "🤖 <b>Примеры естественного языка:</b>\n\n"
            "• <code>Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту</code>\n"
            "• <code>Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890</code>\n"
            "• <code>Оплати инстаграм 200$ проект Гамма счет 1234-5678</code>\n"
            "• <code>Требуется оплата тикток 75$ для проекта Дельта, прикрепляю файл</code>\n"
            "• <code>Мне нужно оплатить YouTube рекламу на 300 баксов для проекта Эпсилон через кошелек 0x123abc</code>",
            parse_mode="HTML"
        )
    
    # Примеры для финансистов
    elif callback_data == "example_confirmation":
        await callback.message.answer(
            "✅ <b>Примеры подтверждения оплаты:</b>\n\n"
            "• <code>Оплачено 123</code> + скриншот\n"
            "• <code>Оплачено 124, хэш: 0xabc123...</code>\n"
            "• <code>Оплачено 125</code> + чек об оплате\n\n"
            "Обязательно прикрепите файл подтверждения!",
            parse_mode="HTML"
        )
    elif callback_data == "example_balance_commands":
        await callback.message.answer(
            "📋 <b>Команды баланса для финансистов:</b>\n\n"
            "• <code>Покажи баланс</code> / <code>Сколько денег?</code>\n"
            "• <code>Текущий баланс</code> / <code>Баланс счета</code>\n"
            "• <code>/balance</code> (классическая команда)\n\n"
            "Все команды работают с естественным языком!",
            parse_mode="HTML"
        )
    
    # Примеры для руководителей  
    elif callback_data == "example_balance_classic":
        await callback.message.answer(
            "💵 <b>Классическое пополнение баланса:</b>\n\n"
            "• <code>Added 1000$</code>\n"
            "• <code>Added 500$ пополнение от клиента X</code>\n"
            "• <code>Added 750$ поступление от проекта Y</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_balance_natural":
        await callback.message.answer(
            "🤖 <b>Пополнение естественным языком:</b>\n\n"
            "• <code>Пополнение 1000</code>\n"
            "• <code>Добавить 500 на баланс</code>\n"
            "• <code>Закинь 200 долларов от клиента Альфа</code>\n"
            "• <code>Получили оплату 850$ от заказчика</code>\n"
            "• <code>Нужно добавить 2000 долларов</code>\n"
            "• <code>Баланс пополнить на 1500</code>",
            parse_mode="HTML"
        )
    elif callback_data == "example_stats_commands":
        await callback.message.answer(
            "📊 <b>Команды статистики:</b>\n\n"
            "• <code>Статистика</code> / <code>Покажи отчет</code>\n"
            "• <code>Как дела?</code> / <code>Общая статистика</code>\n"
            "• <code>Покажи баланс</code> / <code>Сколько денег?</code>\n"
            "• <code>/stats</code> / <code>/balance</code> (классические команды)",
            parse_mode="HTML"
        )
    
    # Быстрые действия
    elif callback_data == "quick_balance":
        from handlers.financier import balance_command_handler
        await balance_command_handler(callback.message)
    elif callback_data == "quick_stats":
        from handlers.manager import statistics_handler
        await statistics_handler(callback.message)
    elif callback_data.startswith("quick_"):
        await callback.message.answer(
            f"🚀 <b>Быстрое действие: {callback_data}</b>\n\n"
            "Функция в разработке...",
            parse_mode="HTML"
        )
    
    await callback.answer()


def setup_menu_handlers(dp: Dispatcher):
    """Регистрация обработчиков меню"""
    
    def is_authorized(message):
        return Config.is_authorized(message.from_user.id)
    
    def is_authorized_callback(callback):
        return Config.is_authorized(callback.from_user.id)
    
    # Команда меню
    dp.message.register(
        lambda msg: show_main_menu(msg, Config.get_user_role(msg.from_user.id)),
        Command("menu"),
        is_authorized
    )
    
    # Обработчик кнопок меню отключен (reply кнопки убраны)
    # dp.message.register(
    #     menu_button_handler,
    #     F.text.regexp(r"^[📋🏠💳📝💰✅📊💵📈🚀]"),
    #     is_authorized
    # )
    
    # Обработчик callback-запросов
    dp.callback_query.register(
        callback_handler,
        is_authorized_callback
    )