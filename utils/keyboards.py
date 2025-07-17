"""
Модуль для создания интерактивных клавиатур и меню бота.
Содержит клавиатуры для разных ролей пользователей.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_main_menu_keyboard(user_role: str) -> ReplyKeyboardMarkup:
    """
    Создает основное меню с кнопками для конкретной роли
    
    Args:
        user_role: Роль пользователя (marketer, financier, manager)
        
    Returns:
        ReplyKeyboardMarkup с кнопками команд
    """
    builder = ReplyKeyboardBuilder()
    
    # Общие команды для всех ролей
    builder.add(KeyboardButton(text="📋 Справка"))
    builder.add(KeyboardButton(text="🏠 Главное меню"))
    
    if user_role == "marketer":
        # Кнопки для маркетологов
        builder.add(KeyboardButton(text="💳 Создать заявку на оплату"))
        builder.add(KeyboardButton(text="📝 Примеры заявок"))
        
    elif user_role == "financier":
        # Кнопки для финансистов
        builder.add(KeyboardButton(text="💰 Показать баланс"))
        builder.add(KeyboardButton(text="✅ Подтвердить оплату"))
        builder.add(KeyboardButton(text="📊 Мои операции"))
        
    elif user_role == "manager":
        # Кнопки для руководителей
        builder.add(KeyboardButton(text="💰 Показать баланс"))
        builder.add(KeyboardButton(text="📊 Статистика"))
        builder.add(KeyboardButton(text="💵 Пополнить баланс"))
        builder.add(KeyboardButton(text="📈 Отчеты"))
    
    # Настройка размера клавиатуры
    builder.adjust(2)  # По 2 кнопки в ряд
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие или напишите сообщение..."
    )


def get_examples_keyboard(user_role: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с примерами для конкретной роли
    
    Args:
        user_role: Роль пользователя
        
    Returns:
        InlineKeyboardMarkup с примерами
    """
    builder = InlineKeyboardBuilder()
    
    if user_role == "marketer":
        builder.add(InlineKeyboardButton(
            text="💳 Криптовалюта", 
            callback_data="example_crypto"
        ))
        builder.add(InlineKeyboardButton(
            text="📱 Телефон", 
            callback_data="example_phone"
        ))
        builder.add(InlineKeyboardButton(
            text="💰 Счет", 
            callback_data="example_account"
        ))
        builder.add(InlineKeyboardButton(
            text="📄 Файл", 
            callback_data="example_file"
        ))
        builder.add(InlineKeyboardButton(
            text="🤖 Естественный язык", 
            callback_data="example_natural"
        ))
        
    elif user_role == "financier":
        builder.add(InlineKeyboardButton(
            text="✅ Подтверждение оплаты", 
            callback_data="example_confirmation"
        ))
        builder.add(InlineKeyboardButton(
            text="📋 Команды баланса", 
            callback_data="example_balance_commands"
        ))
        
    elif user_role == "manager":
        builder.add(InlineKeyboardButton(
            text="💵 Пополнение классическое", 
            callback_data="example_balance_classic"
        ))
        builder.add(InlineKeyboardButton(
            text="🤖 Пополнение естественным языком", 
            callback_data="example_balance_natural"
        ))
        builder.add(InlineKeyboardButton(
            text="📊 Команды статистики", 
            callback_data="example_stats_commands"
        ))
    
    builder.adjust(2)  # По 2 кнопки в ряд
    
    return builder.as_markup()


def get_quick_actions_keyboard(user_role: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру быстрых действий
    
    Args:
        user_role: Роль пользователя
        
    Returns:
        InlineKeyboardMarkup с быстрыми действиями
    """
    builder = InlineKeyboardBuilder()
    
    if user_role == "marketer":
        builder.add(InlineKeyboardButton(
            text="🚀 Быстрая заявка Facebook", 
            callback_data="quick_facebook"
        ))
        builder.add(InlineKeyboardButton(
            text="🚀 Быстрая заявка Google", 
            callback_data="quick_google"
        ))
        builder.add(InlineKeyboardButton(
            text="🚀 Быстрая заявка Instagram", 
            callback_data="quick_instagram"
        ))
        
    elif user_role == "financier":
        builder.add(InlineKeyboardButton(
            text="💰 Быстрый баланс", 
            callback_data="quick_balance"
        ))
        builder.add(InlineKeyboardButton(
            text="📋 Последние операции", 
            callback_data="quick_operations"
        ))
        
    elif user_role == "manager":
        builder.add(InlineKeyboardButton(
            text="📊 Быстрая статистика", 
            callback_data="quick_stats"
        ))
        builder.add(InlineKeyboardButton(
            text="💵 Быстрое пополнение", 
            callback_data="quick_add_balance"
        ))
        builder.add(InlineKeyboardButton(
            text="📈 Сводка дня", 
            callback_data="quick_daily_summary"
        ))
    
    builder.adjust(2)
    
    return builder.as_markup()


def remove_keyboard() -> ReplyKeyboardMarkup:
    """Удаляет клавиатуру"""
    return ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
        one_time_keyboard=True
    )