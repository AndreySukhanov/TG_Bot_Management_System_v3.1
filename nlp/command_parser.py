"""
Универсальный NLP парсер команд для естественного языка.
Распознает команды start, help, balance, stats через ИИ.
"""

import json
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from utils.config import Config

logger = logging.getLogger(__name__)


class CommandNLPParser:
    """Класс для NLP-парсинга команд бота"""
    
    def __init__(self):
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        
        # Системный промпт для GPT-4
        self.system_prompt = """
Ты — специалист по распознаванию команд чат-бота. Твоя задача — определить, какую команду хочет выполнить пользователь.

Доступные команды:
1. "start" - начать работу, приветствие, главное меню
2. "help" - справка, помощь, что умеет бот
3. "balance" - показать баланс, сколько денег, текущее состояние счета
4. "stats" - статистика, отчет, показать данные

Примеры:
- "Привет" → command: "start"
- "Начать работу" → command: "start"
- "Покажи справку" → command: "help"
- "Что ты умеешь?" → command: "help"
- "Помощь" → command: "help"
- "Сколько денег на счету?" → command: "balance"
- "Покажи баланс" → command: "balance"
- "Текущий баланс" → command: "balance"
- "Статистика" → command: "stats"
- "Покажи отчет" → command: "stats"
- "Как дела?" → command: "stats"

Если сообщение НЕ является командой (например, запрос на оплату или пополнение), возвращай null.

Возвращай ТОЛЬКО JSON без дополнительного текста в формате:
{
    "command": "название_команды_или_null",
    "confidence": число_от_0_до_1
}

Confidence - это уверенность в распознавании (1.0 = очень уверен, 0.5 = не очень уверен).
"""
    
    async def parse_command(self, text: str, user_role: str = None) -> Optional[Dict[str, Any]]:
        """
        Парсинг команды с использованием GPT-4 mini
        
        Args:
            text: Текст сообщения от пользователя
            user_role: Роль пользователя (для фильтрации доступных команд)
            
        Returns:
            Словарь с командой или None если не команда
        """
        if not text or not text.strip():
            return None
            
        text = text.strip()
        logger.info(f"NLP парсинг команды: {text}")
        
        try:
            # Отправка запроса к OpenAI
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            # Получение ответа
            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI ответ для команды: {content}")
            
            # Парсинг JSON ответа
            try:
                command_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON команды: {e}")
                return None
            
            # Валидация команды
            if not self._validate_command(command_data, user_role):
                return None
            
            logger.info(f"Успешно распознана команда: {command_data}")
            return command_data
            
        except Exception as e:
            logger.error(f"Ошибка NLP парсинга команды: {e}")
            return None
    
    def _validate_command(self, data: Dict[str, Any], user_role: str = None) -> bool:
        """Валидация команды"""
        if not isinstance(data, dict):
            return False
        
        command = data.get("command")
        confidence = data.get("confidence", 0)
        
        # Если команда null, это не команда
        if command is None:
            logger.info("Сообщение не является командой")
            return False
        
        # Проверка доступных команд
        valid_commands = ["start", "help", "balance", "stats"]
        if command not in valid_commands:
            logger.warning(f"Неизвестная команда: {command}")
            return False
        
        # Проверка прав доступа по ролям
        if user_role and not self._check_command_permission(command, user_role):
            logger.warning(f"Команда {command} недоступна для роли {user_role}")
            return False
        
        # Проверка уверенности (принимаем команды с confidence >= 0.5)
        if confidence < 0.5:
            logger.info(f"Низкая уверенность в команде: {confidence}")
            return False
        
        return True
    
    def _check_command_permission(self, command: str, user_role: str) -> bool:
        """Проверка прав доступа к команде по роли"""
        # Права доступа к командам
        permissions = {
            "start": ["marketer", "financier", "manager"],  # Все роли
            "help": ["marketer", "financier", "manager"],   # Все роли
            "balance": ["financier", "manager"],            # Только финансисты и руководители
            "stats": ["manager"]                            # Только руководители
        }
        
        allowed_roles = permissions.get(command, [])
        return user_role in allowed_roles
    
    async def test_connection(self) -> bool:
        """Тест подключения к OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к OpenAI для команд: {e}")
            return False
    
    def get_examples(self) -> Dict[str, str]:
        """Возвращает примеры команд в естественном языке"""
        return {
            "start_examples": [
                "Привет",
                "Начать работу",
                "Старт",
                "Добро пожаловать"
            ],
            "help_examples": [
                "Покажи справку",
                "Что ты умеешь?",
                "Помощь",
                "Справка по боту",
                "Как пользоваться?"
            ],
            "balance_examples": [
                "Покажи баланс",
                "Сколько денег?",
                "Текущий баланс",
                "Сколько на счету?",
                "Баланс счета"
            ],
            "stats_examples": [
                "Статистика",
                "Покажи отчет",
                "Как дела?",
                "Общая статистика",
                "Отчет по системе"
            ]
        }