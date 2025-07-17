"""
Модуль для управления командами бота.
Настраивает меню команд (/) для разных ролей пользователей.
"""

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat
from utils.config import Config
import logging

logger = logging.getLogger(__name__)


class BotCommandManager:
    """Класс для управления командами бота"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.config = Config()
    
    def get_commands_for_role(self, role: str) -> list[BotCommand]:
        """
        Возвращает список команд для конкретной роли
        
        Args:
            role: Роль пользователя (marketer, financier, manager)
            
        Returns:
            Список BotCommand для роли
        """
        # Общие команды для всех ролей
        base_commands = [
            BotCommand(command="start", description="🏠 Главное меню"),
            BotCommand(command="help", description="📋 Справка и помощь"),
        ]
        
        # Добавляем menu только для маркетологов
        common_commands = base_commands.copy()
        if role == "marketer":
            common_commands.append(BotCommand(command="menu", description="🎛️ Показать меню"))
        
        role_commands = {
            "marketer": [
                # Только 2 команды для маркетолога
            ],
            "financier": [
                BotCommand(command="balance", description="💰 Показать баланс"),
            ],
            "manager": [
                BotCommand(command="balance", description="💰 Показать баланс"),
                BotCommand(command="stats", description="📊 Статистика системы"),
                BotCommand(command="ai", description="🤖 AI-помощник для аналитики"),
                BotCommand(command="dashboard", description="📊 Веб-дашборд аналитики"),
                BotCommand(command="resetbalance", description="⚠️ Обнулить баланс"),
            ]
        }
        
        # Объединяем общие команды с ролевыми
        commands = common_commands.copy()
        if role in role_commands:
            commands.extend(role_commands[role])
        
        return commands
    
    async def set_default_commands(self):
        """Устанавливает команды по умолчанию для всех пользователей"""
        default_commands = [
            BotCommand(command="start", description="🏠 Начать работу"),
            BotCommand(command="help", description="📋 Получить справку"),
        ]
        
        try:
            await self.bot.set_my_commands(default_commands)
            logger.info("Установлены команды по умолчанию")
        except Exception as e:
            logger.error(f"Ошибка установки команд по умолчанию: {e}")
    
    async def set_commands_for_user(self, user_id: int, role: str):
        """
        Устанавливает персональные команды для пользователя
        
        Args:
            user_id: ID пользователя
            role: Роль пользователя
        """
        commands = self.get_commands_for_role(role)
        
        try:
            await self.bot.set_my_commands(
                commands=commands,
                scope=BotCommandScopeChat(chat_id=user_id)
            )
            logger.info(f"Установлены команды для пользователя {user_id} с ролью {role}")
        except Exception as e:
            logger.error(f"Ошибка установки команд для пользователя {user_id}: {e}")
    
    async def update_all_user_commands(self):
        """Обновляет команды для всех авторизованных пользователей"""
        all_users = set()
        
        # Собираем всех пользователей из всех ролей
        all_users.update(self.config.MARKETERS)
        all_users.update(self.config.FINANCIERS) 
        all_users.update(self.config.MANAGERS)
        
        for user_id in all_users:
            role = self.config.get_user_role(user_id)
            if role != "unknown":
                await self.set_commands_for_user(user_id, role)
        
        logger.info(f"Обновлены команды для {len(all_users)} пользователей")
    
    def get_command_descriptions(self, role: str) -> dict:
        """
        Возвращает описания команд для роли
        
        Args:
            role: Роль пользователя
            
        Returns:
            Словарь команда: описание
        """
        descriptions = {
            "marketer": {
                "/start": "Главное меню с кнопками",
                "/help": "Подробная справка по функциям",
                "/menu": "Показать интерактивное меню",
                "/examples": "Примеры заявок на оплату",
                "/formats": "Поддерживаемые форматы сообщений",
                "/natural": "Примеры естественного языка"
            },
            "financier": {
                "/start": "Главное меню с кнопками", 
                "/help": "Подробная справка по функциям",
                "/menu": "Показать интерактивное меню",
                "/balance": "Показать текущий баланс",
                "/confirm": "Инструкции по подтверждению оплат",
                "/operations": "История моих операций"
            },
            "manager": {
                "/start": "Главное меню с кнопками",
                "/help": "Подробная справка по функциям", 
                "/menu": "Показать интерактивное меню",
                "/balance": "Показать баланс и статистику",
                "/stats": "Подробная статистика системы",
                "/ai": "AI-помощник для получения аналитики",
                "/resetbalance": "Обнулить баланс системы",
                "/addbalance": "Инструкции по пополнению баланса",
                "/reports": "Различные отчеты системы",
                "/summary": "Сводка за день"
            }
        }
        
        return descriptions.get(role, {})