"""
Гибридный парсер, объединяющий regex и NLP подходы.
Сначала пытается использовать regex, если не получается - использует NLP.
"""

import logging
from typing import Optional, Dict, Any
from .parser import PaymentParser
from .nlp_parser import NLPPaymentParser

logger = logging.getLogger(__name__)


class HybridPaymentParser:
    """Гибридный парсер заявок на оплату"""
    
    def __init__(self):
        self.regex_parser = PaymentParser()
        self.nlp_parser = NLPPaymentParser()
    
    async def parse_payment_message(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг сообщения о платеже с использованием гибридного подхода
        
        Args:
            text: Текст сообщения от маркетолога
            
        Returns:
            Словарь с данными о платеже или None если парсинг не удался
        """
        if not text or not text.strip():
            return None
            
        text = text.strip()
        logger.info(f"Гибридный парсинг сообщения: {text}")
        
        # Сначала пытаемся regex парсинг (быстрый и точный для структурированных сообщений)
        try:
            regex_result = await self.regex_parser.parse_payment_message(text)
            if regex_result and self.regex_parser.validate_payment_data(regex_result):
                logger.info("Успешно распарсено с помощью regex")
                return regex_result
            else:
                logger.info("Regex парсинг не удался, переходим к NLP")
        except Exception as e:
            logger.warning(f"Ошибка regex парсинга: {e}")
        
        # Если regex не справился, используем NLP парсинг
        try:
            nlp_result = await self.nlp_parser.parse_payment_message(text)
            if nlp_result:
                logger.info("Успешно распарсено с помощью NLP")
                return nlp_result
            else:
                logger.warning("NLP парсинг также не удался")
        except Exception as e:
            logger.error(f"Ошибка NLP парсинга: {e}")
        
        logger.error("Оба метода парсинга не смогли обработать сообщение")
        return None
    
    def validate_payment_data(self, payment_data: Dict[str, Any]) -> bool:
        """Валидация извлеченных данных о платеже"""
        return self.regex_parser.validate_payment_data(payment_data)
    
    def get_examples(self) -> Dict[str, str]:
        """Возвращает примеры правильного формата сообщений"""
        regex_examples = self.regex_parser.get_examples()
        nlp_examples = self.nlp_parser.get_examples()
        
        # Объединяем примеры
        all_examples = {**regex_examples, **nlp_examples}
        
        # Добавляем дополнительные примеры для демонстрации возможностей
        all_examples.update({
            "hybrid_1": "Структурированное: Нужна оплата сервиса Facebook на сумму 100$ для проекта Alpha, криптовалюта: 0x123...",
            "hybrid_2": "Естественное: Привет, мне нужно оплатить фейсбук на сотку для проекта Альфа через крипту"
        })
        
        return all_examples
    
    async def test_connection(self) -> Dict[str, bool]:
        """Тест подключения к обоим парсерам"""
        results = {
            "regex": True,  # Regex парсер всегда работает
            "nlp": await self.nlp_parser.test_connection()
        }
        
        logger.info(f"Результаты тестирования подключения: {results}")
        return results