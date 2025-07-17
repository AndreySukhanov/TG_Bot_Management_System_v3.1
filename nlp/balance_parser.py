"""
NLP парсер для операций с балансом руководителей.
Использует OpenAI GPT-4 mini для понимания естественного языка.
"""

import json
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from utils.config import Config

logger = logging.getLogger(__name__)


class BalanceNLPParser:
    """Класс для NLP-парсинга операций с балансом"""
    
    def __init__(self):
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        
        # Системный промпт для GPT-4
        self.system_prompt = """
Ты — специалист по обработке операций с балансом. Твоя задача — извлечь структурированные данные из текста о пополнении баланса.

Анализируй текст и извлекай следующую информацию:
1. operation_type (тип операции: "add_balance" для пополнения)
2. amount (сумма в долларах США, только число)
3. description (описание операции, если есть)

Примеры:
- "Пополнение 1000" → operation_type: "add_balance", amount: 1000, description: ""
- "Добавить 500 на баланс" → operation_type: "add_balance", amount: 500, description: ""
- "Закинь 200 долларов от клиента Альфа" → operation_type: "add_balance", amount: 200, description: "от клиента Альфа"
- "Added 1000$ пополнение от партнера" → operation_type: "add_balance", amount: 1000, description: "пополнение от партнера"
- "300$ поступление от проекта Бета" → operation_type: "add_balance", amount: 300, description: "поступление от проекта Бета"

Возвращай ТОЛЬКО JSON без дополнительного текста в формате:
{
    "operation_type": "add_balance",
    "amount": число,
    "description": "описание или пустая строка"
}

Если операция не связана с пополнением баланса, возвращай null для operation_type.
"""
    
    async def parse_balance_message(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг сообщения о балансе с использованием GPT-4 mini
        
        Args:
            text: Текст сообщения от руководителя
            
        Returns:
            Словарь с данными об операции или None если парсинг не удался
        """
        if not text or not text.strip():
            return None
            
        text = text.strip()
        logger.info(f"NLP парсинг баланса: {text}")
        
        try:
            # Отправка запроса к OpenAI
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.1
            )
            
            # Получение ответа
            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI ответ для баланса: {content}")
            
            # Парсинг JSON ответа
            try:
                balance_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON ответа баланса: {e}")
                return None
            
            # Валидация данных
            if not self._validate_balance_data(balance_data):
                logger.warning("Данные баланса не прошли валидацию")
                return None
            
            # Нормализация данных
            normalized_data = self._normalize_balance_data(balance_data)
            
            logger.info(f"Успешно распарсено NLP баланс: {normalized_data}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"Ошибка NLP парсинга баланса: {e}")
            return None
    
    def _validate_balance_data(self, data: Dict[str, Any]) -> bool:
        """Валидация данных, полученных от GPT-4"""
        if not isinstance(data, dict):
            return False
        
        # Проверка типа операции
        if data.get("operation_type") != "add_balance":
            logger.info("Операция не является пополнением баланса")
            return False
        
        # Проверка суммы
        amount = data.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0:
            logger.warning("Неверный тип или значение amount")
            return False
        
        return True
    
    def _normalize_balance_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализация данных"""
        normalized = {
            "operation_type": data["operation_type"],
            "amount": float(data["amount"]),
            "description": str(data.get("description", "")).strip()
        }
        
        return normalized
    
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
            logger.error(f"Ошибка подключения к OpenAI для баланса: {e}")
            return False
    
    def get_examples(self) -> Dict[str, str]:
        """Возвращает примеры правильного формата сообщений"""
        return {
            "natural_1": "Пополнение 1000",
            "natural_2": "Добавить 500 на баланс",
            "natural_3": "Закинь 200 долларов от клиента Альфа",
            "natural_4": "Added 1000$ пополнение от партнера",
            "natural_5": "300$ поступление от проекта Бета",
            "natural_6": "Пополни баланс на 750 от клиента Гамма"
        }