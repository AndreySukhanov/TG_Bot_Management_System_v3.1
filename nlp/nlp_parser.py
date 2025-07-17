"""
Улучшенный NLP-парсер заявок на оплату с использованием OpenAI GPT-4 mini.
Обрабатывает естественный язык и извлекает данные из произвольного текста.
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from utils.config import Config

logger = logging.getLogger(__name__)


class NLPPaymentParser:
    """Класс для NLP-парсинга заявок на оплату с использованием GPT-4 mini"""
    
    def __init__(self):
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        
        # Системный промпт для GPT-4
        self.system_prompt = """
Ты — специалист по обработке заявок на оплату. Твоя задача — извлечь структурированные данные из текста заявки на оплату.

Анализируй текст и извлекай следующую информацию:
1. service_name (название сервиса для оплаты)
2. amount (сумма в долларах США, только число)
3. project_name (название проекта)
4. payment_method (способ оплаты: "crypto", "phone", "account", "file")
5. payment_details (детали оплаты: адрес кошелька, номер телефона, реквизиты счета и т.д.)

Примеры:
- "Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту" → service_name: "Facebook", amount: 100, project_name: "Альфа", payment_method: "crypto"
- "Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890" → service_name: "Google Ads", amount: 50, project_name: "Бета", payment_method: "phone", payment_details: "+1234567890"
- "Оплати инстаграм 200$ проект Гамма счет 1234-5678" → service_name: "Instagram", amount: 200, project_name: "Гамма", payment_method: "account", payment_details: "1234-5678"

Возвращай ТОЛЬКО JSON без дополнительного текста в формате:
{
    "service_name": "название сервиса",
    "amount": число,
    "project_name": "название проекта",
    "payment_method": "способ оплаты",
    "payment_details": "детали оплаты или пустая строка"
}

Если какая-то информация отсутствует, возвращай null для этого поля.
"""
    
    async def parse_payment_message(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг сообщения о платеже с использованием GPT-4 mini
        
        Args:
            text: Текст сообщения от маркетолога
            
        Returns:
            Словарь с данными о платеже или None если парсинг не удался
        """
        if not text or not text.strip():
            return None
            
        text = text.strip()
        logger.info(f"NLP парсинг сообщения: {text}")
        
        try:
            # Отправка запроса к OpenAI
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            # Получение ответа
            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI ответ: {content}")
            
            # Парсинг JSON ответа
            try:
                payment_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON ответа: {e}")
                return None
            
            # Валидация и очистка данных
            if not self._validate_parsed_data(payment_data):
                logger.warning("Данные не прошли валидацию")
                return None
            
            # Нормализация данных
            normalized_data = self._normalize_data(payment_data)
            
            logger.info(f"Успешно распарсено с помощью NLP: {normalized_data}")
            return normalized_data
            
        except Exception as e:
            logger.error(f"Ошибка NLP парсинга: {e}")
            return None
    
    def _validate_parsed_data(self, data: Dict[str, Any]) -> bool:
        """Валидация данных, полученных от GPT-4"""
        if not isinstance(data, dict):
            return False
        
        # Проверка обязательных полей
        required_fields = ["service_name", "amount", "project_name", "payment_method"]
        for field in required_fields:
            if field not in data or data[field] is None:
                logger.warning(f"Отсутствует обязательное поле: {field}")
                return False
        
        # Проверка типов данных
        if not isinstance(data["service_name"], str) or not data["service_name"].strip():
            logger.warning("Неверный тип или пустое значение service_name")
            return False
        
        if not isinstance(data["amount"], (int, float)) or data["amount"] <= 0:
            logger.warning("Неверный тип или значение amount")
            return False
        
        if not isinstance(data["project_name"], str) or not data["project_name"].strip():
            logger.warning("Неверный тип или пустое значение project_name")
            return False
        
        # Проверка метода оплаты
        valid_methods = ["crypto", "phone", "account", "file"]
        if data["payment_method"] not in valid_methods:
            logger.warning(f"Неверный метод оплаты: {data['payment_method']}")
            return False
        
        return True
    
    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализация данных"""
        normalized = {
            "service_name": data["service_name"].strip(),
            "amount": float(data["amount"]),
            "project_name": data["project_name"].strip(),
            "payment_method": data["payment_method"].lower(),
            "payment_details": str(data.get("payment_details", "")).strip()
        }
        
        # Нормализация названий сервисов
        service_mappings = {
            "facebook": "Facebook Ads",
            "фейсбук": "Facebook Ads",
            "fb": "Facebook Ads",
            "google ads": "Google Ads",
            "гугл": "Google Ads",
            "гугл адс": "Google Ads",
            "instagram": "Instagram Ads",
            "инстаграм": "Instagram Ads",
            "insta": "Instagram Ads",
            "tiktok": "TikTok Ads",
            "тикток": "TikTok Ads",
            "youtube": "YouTube Ads",
            "ютуб": "YouTube Ads"
        }
        
        service_lower = normalized["service_name"].lower()
        for key, value in service_mappings.items():
            if key in service_lower:
                normalized["service_name"] = value
                break
        
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
            logger.error(f"Ошибка подключения к OpenAI: {e}")
            return False
    
    def get_examples(self) -> Dict[str, str]:
        """Возвращает примеры правильного формата сообщений"""
        return {
            "natural_1": "Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту",
            "natural_2": "Нужна оплата гугл адс 50 долларов проект Бета телефон +1234567890",
            "natural_3": "Оплати инстаграм 200$ проект Гамма счет 1234-5678",
            "natural_4": "Требуется оплата тикток 75$ для проекта Дельта, прикрепляю файл с реквизитами"
        }