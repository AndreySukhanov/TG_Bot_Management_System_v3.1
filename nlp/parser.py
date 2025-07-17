"""
Парсер сообщений для извлечения данных о платежах.
Использует регулярные выражения для парсинга текста от маркетологов.
"""

import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PaymentParser:
    """Класс для парсинга заявок на оплату"""
    
    def __init__(self):
        # Паттерны для извлечения данных (улучшенные)
        self.service_patterns = [
            r"сервиса?\s+([^на]+?)(?=\s+на)",
            r"оплат[ауь]\s+сервиса?\s+([^на]+?)(?=\s+на)",
            r"оплат[ауь]\s+([^на]+?)(?=\s+на)",
            r"(?:для|за)\s+([^на]+?)(?=\s+на\s+сумму)"
        ]
        
        self.amount_patterns = [
            r"(?:на\s+сумму\s+|на\s+)\[?(\d+(?:[.,]\d+)?)\]?\s*[\$₽]",
            r"\[?(\d+(?:[.,]\d+)?)\]?\s*[\$₽]",
            r"сумма[:\s]+\[?(\d+(?:[.,]\d+)?)\]?\s*[\$₽]"
        ]
        
        self.project_patterns = [
            r"(?:для\s+)?проекта?\s+([^,]+?)(?=,|$)",
            r"проект[:\s]+([^,]+?)(?=,|$)",
            r"по\s+проекту\s+([^,]+?)(?=,|$)"
        ]
        
        # Паттерны для методов оплаты (исправленные)
        self.crypto_patterns = [
            r"криптовалют[ауы][:=\s]*([0-9a-fA-FxX]{10,})",
            r"кошел[её]к[:=\s]*([0-9a-fA-FxX]{10,})",
            r"адрес[:=\s]*([0-9a-fA-FxX]{10,})",
            r"0x[0-9a-fA-F]{10,}",
            r"[0-9a-fA-F]{20,}"
        ]
        
        self.phone_patterns = [
            r"(?:номер\s+)?телефон[ауы]?[:=\s]*([\+\d\-\(\)\s]{7,})",
            r"тел\.?[:=\s]*([\+\d\-\(\)\s]{7,})",
            r"моб\.?[:=\s]*([\+\d\-\(\)\s]{7,})"
        ]
        
        self.account_patterns = [
            r"счет[её]?[:=\s]*([^,]+?)(?=,|$)",
            r"карт[ауы][:=\s]*([^,]+?)(?=,|$)",
            r"реквизит[ыи][:=\s]*([^,]+?)(?=,|$)"
        ]
        
    async def parse_payment_message(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг сообщения о платеже
        
        Args:
            text: Текст сообщения от маркетолога
            
        Returns:
            Словарь с данными о платеже или None если парсинг не удался
        """
        if not text:
            return None
            
        text = text.strip()
        logger.info(f"Парсинг сообщения: {text}")
        
        try:
            # Извлечение названия сервиса
            service_name = self._extract_service_name(text)
            if not service_name:
                logger.warning("Не удалось извлечь название сервиса")
                return None
            
            # Извлечение суммы
            amount = self._extract_amount(text)
            if not amount:
                logger.warning("Не удалось извлечь сумму")
                return None
            
            # Извлечение названия проекта
            project_name = self._extract_project_name(text)
            if not project_name:
                logger.warning("Не удалось извлечь название проекта")
                return None
            
            # Определение метода оплаты и деталей
            payment_method, payment_details = self._extract_payment_method(text)
            if not payment_method:
                logger.warning("Не удалось определить метод оплаты")
                return None
            
            result = {
                "service_name": service_name.strip(),
                "amount": amount,
                "project_name": project_name.strip(),
                "payment_method": payment_method,
                "payment_details": payment_details.strip() if payment_details else ""
            }
            
            logger.info(f"Успешно распарсено: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга сообщения: {e}")
            return None
    
    def _extract_service_name(self, text: str) -> Optional[str]:
        """Извлечение названия сервиса"""
        for pattern in self.service_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                service = match.group(1).strip()
                # Удаляем лишние слова
                service = re.sub(r'^(оплата|нужна|требуется)\s+', '', service, flags=re.IGNORECASE)
                return service
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Извлечение суммы платежа"""
        for pattern in self.amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1)
                    # Замена запятой на точку для корректной конвертации
                    amount_str = amount_str.replace(',', '.').replace(' ', '')
                    return float(amount_str)
                except ValueError:
                    continue
        return None
    
    def _extract_project_name(self, text: str) -> Optional[str]:
        """Извлечение названия проекта"""
        for pattern in self.project_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                project = match.group(1).strip()
                # Удаляем лишние символы и слова
                project = re.sub(r'^(для\s+)', '', project, flags=re.IGNORECASE)
                return project
        return None
    
    def _extract_payment_method(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Определение метода оплаты и извлечение деталей"""
        
        # Проверка на криптовалюту (улучшенная)
        for pattern in self.crypto_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    wallet_address = match.group(1)
                else:
                    wallet_address = match.group(0)
                return "crypto", wallet_address
        
        # Проверка на номер телефона
        for pattern in self.phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone_number = match.group(1).strip()
                # Очистка номера телефона
                phone_number = re.sub(r'[^\d\+\-\(\)]', '', phone_number)
                return "phone", phone_number
        
        # Проверка на счет
        for pattern in self.account_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                account_details = match.group(1).strip()
                return "account", account_details
        
        # Fallback: если явно указан способ оплаты без деталей
        if re.search(r"крипто|криптовалюта", text, re.IGNORECASE):
            return "crypto", ""
        if re.search(r"телефон", text, re.IGNORECASE):
            return "phone", ""
        if re.search(r"счет|реквизит|карта", text, re.IGNORECASE):
            return "account", ""
        if re.search(r"файл|qr|код|скан|прикреп", text, re.IGNORECASE):
            return "file", "Файл будет прикреплен"
        
        return None, None
    
    def validate_payment_data(self, payment_data: Dict[str, Any]) -> bool:
        """Валидация извлеченных данных о платеже"""
        required_fields = ["service_name", "amount", "project_name", "payment_method"]
        
        for field in required_fields:
            if field not in payment_data or not payment_data[field]:
                logger.warning(f"Отсутствует обязательное поле: {field}")
                return False
        
        # Проверка суммы
        if payment_data["amount"] <= 0:
            logger.warning("Сумма должна быть больше нуля")
            return False
        
        # Проверка метода оплаты
        valid_methods = ["crypto", "phone", "account", "file"]
        if payment_data["payment_method"] not in valid_methods:
            logger.warning(f"Неверный метод оплаты: {payment_data['payment_method']}")
            return False
        
        return True
    
    def get_examples(self) -> Dict[str, str]:
        """Возвращает примеры правильного формата сообщений"""
        return {
            "crypto": "Нужна оплата сервиса Facebook Ads на сумму 100$ для проекта Alpha, криптовалюта: 0x1234567890abcdef",
            "phone": "Оплата сервиса Google Ads на 50$ для проекта Beta, номер телефона: +1234567890",
            "account": "Оплата сервиса Instagram на 200$ для проекта Gamma, счет: 1234-5678-9012-3456",
            "file": "Нужна оплата сервиса TikTok на 75$ для проекта Delta, счет: прикрепленный файл"
        } 