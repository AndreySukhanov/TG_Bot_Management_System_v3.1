"""
AI-помощник для руководителя
Обрабатывает запросы на естественном языке и предоставляет аналитику
"""

import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from db.database import BalanceDB, PaymentDB
from utils.config import Config
import aiosqlite


@dataclass
class AnalyticsData:
    """Структура для хранения аналитических данных"""
    balance: float
    pending_payments: List[Dict]
    team_size: int
    today_payments: int
    weekly_payments: List[Dict]
    projects: List[Dict]
    recent_operations: List[Dict]
    balance_history: List[Dict]


class ManagerAIAssistant:
    """AI-помощник для руководителя"""
    
    def __init__(self):
        self.config = Config()
        self.intent_patterns = {
            'balance': [
                r'баланс\w*',
                r'сколько\s+денег',
                r'сколько\s+средств',
                r'денежны\w+\s+состояние',
                r'финансовы\w+\s+состояние',
                r'сколько\s+у\s+нас',
                r'текущи\w+\s+баланс'
            ],
            'pending_payments': [
                r'ожидающи\w+\s+оплат\w*',
                r'платежи?\s+в\s+ожидании',
                r'неоплаченны\w+\s+платежи?',
                r'сколько\s+платежей\s+ждет',
                r'платежи?\s+на\s+рассмотрении',
                r'заявки?\s+на\s+оплату'
            ],
            'today_payments': [
                r'платежи?\s+сегодня',
                r'оплаты?\s+сегодня',
                r'сегодняшни\w+\s+платежи?',
                r'что\s+оплатили\s+сегодня',
                r'сколько\s+платежей\s+сегодня'
            ],
            'team_size': [
                r'команд\w*',
                r'сколько\s+человек',
                r'сколько\s+людей',
                r'размер\s+команды',
                r'состав\s+команды',
                r'пользователи?',
                r'сотрудники?'
            ],
            'weekly_payments': [
                r'платежи?\s+за\s+неделю',
                r'недельны\w+\s+платежи?',
                r'эт\w+\s+неделю?\s+платежи?',
                r'платежи?\s+за\s+7\s+дней',
                r'недельна\w+\s+статистика'
            ],
            'projects': [
                r'проекты?',
                r'какие\s+проекты',
                r'список\s+проектов',
                r'все\s+проекты',
                r'проектна\w+\s+статистика'
            ],
            'recent_operations': [
                r'последни\w+\s+операции?',
                r'недавни\w+\s+операции?',
                r'последни\w+\s+транзакции?',
                r'что\s+происходило',
                r'активность',
                r'последни\w+\s+платежи?'
            ],
            'balance_history': [
                r'истори\w+\s+баланса',
                r'изменения\s+баланса',
                r'как\s+менялся\s+баланс',
                r'динамика\s+баланса',
                r'транзакци\w+\s+истори\w*'
            ]
        }

    async def process_query(self, query: str) -> str:
        """Обработка запроса на естественном языке"""
        try:
            # Нормализация запроса
            normalized_query = self._normalize_query(query)
            
            # Определение намерения
            intent = self._detect_intent(normalized_query)
            
            # Получение данных
            data = await self._get_analytics_data()
            
            # Формирование ответа
            response = await self._generate_response(intent, data, normalized_query)
            
            return response
            
        except Exception as e:
            return f"Извините, произошла ошибка при обработке запроса: {str(e)}"

    def _normalize_query(self, query: str) -> str:
        """Нормализация запроса"""
        # Приведение к нижнему регистру
        query = query.lower().strip()
        
        # Удаление лишних символов
        query = re.sub(r'[^\w\s]', ' ', query)
        
        # Удаление множественных пробелов
        query = re.sub(r'\s+', ' ', query)
        
        return query

    def _detect_intent(self, query: str) -> str:
        """Определение намерения пользователя"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return intent
        
        return 'general'

    async def _get_analytics_data(self) -> AnalyticsData:
        """Получение всех аналитических данных"""
        try:
            # Текущий баланс
            balance = await BalanceDB.get_balance()
            
            # Ожидающие платежи
            pending_payments = await PaymentDB.get_pending_payments()
            
            # Размер команды
            team_size = len(self.config.MARKETERS) + len(self.config.FINANCIERS) + len(self.config.MANAGERS)
            
            # Платежи сегодня
            today_payments = await self._get_today_payments_count()
            
            # Платежи за неделю
            weekly_payments = await self._get_weekly_payments()
            
            # Проекты
            projects = await self._get_projects_stats()
            
            # Последние операции
            recent_operations = await self._get_recent_operations()
            
            # История баланса
            balance_history = await self._get_balance_history()
            
            return AnalyticsData(
                balance=balance,
                pending_payments=pending_payments,
                team_size=team_size,
                today_payments=today_payments,
                weekly_payments=weekly_payments,
                projects=projects,
                recent_operations=recent_operations,
                balance_history=balance_history
            )
            
        except Exception as e:
            raise Exception(f"Ошибка получения данных: {str(e)}")

    async def _get_today_payments_count(self) -> int:
        """Получение количества платежей за сегодня"""
        try:
            async with aiosqlite.connect(self.config.DATABASE_PATH) as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE DATE(created_at) = DATE('now') AND status = 'paid'
                """)
                result = await cursor.fetchone()
                return result[0] if result else 0
        except:
            return 0

    async def _get_weekly_payments(self) -> List[Dict]:
        """Получение платежей за неделю"""
        try:
            async with aiosqlite.connect(self.config.DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("""
                    SELECT * FROM payments 
                    WHERE created_at >= datetime('now', '-7 days')
                    AND status = 'paid'
                    ORDER BY created_at DESC
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except:
            return []

    async def _get_projects_stats(self) -> List[Dict]:
        """Получение статистики по проектам"""
        try:
            async with aiosqlite.connect(self.config.DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("""
                    SELECT 
                        project_name,
                        COUNT(*) as count,
                        SUM(amount) as total,
                        AVG(amount) as avg_amount
                    FROM payments 
                    WHERE project_name IS NOT NULL
                    GROUP BY project_name 
                    ORDER BY total DESC
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except:
            return []

    async def _get_recent_operations(self) -> List[Dict]:
        """Получение последних операций"""
        try:
            async with aiosqlite.connect(self.config.DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("""
                    SELECT * FROM payments 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except:
            return []

    async def _get_balance_history(self) -> List[Dict]:
        """Получение истории баланса"""
        try:
            async with aiosqlite.connect(self.config.DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("""
                    SELECT * FROM balance_history 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except:
            return []

    async def _generate_response(self, intent: str, data: AnalyticsData, query: str) -> str:
        """Генерация ответа на основе намерения и данных"""
        
        if intent == 'balance':
            status = "здоровый" if data.balance >= self.config.LOW_BALANCE_THRESHOLD else "низкий"
            return f"Текущий баланс: ${data.balance:.2f}\nСтатус: {status}"
        
        elif intent == 'pending_payments':
            count = len(data.pending_payments)
            total = sum(p['amount'] for p in data.pending_payments)
            response = f"📝 Ожидающие оплаты: {count} платежей на сумму ${total:.2f}"
            
            if count > 0:
                response += "\n\nПоследние заявки:"
                for payment in data.pending_payments[:5]:
                    response += f"\n• {payment['service_name']} - ${payment['amount']:.2f}"
            
            return response
        
        elif intent == 'today_payments':
            return f"📊 Платежи сегодня: {data.today_payments} завершено"
        
        elif intent == 'team_size':
            marketers = len(self.config.MARKETERS)
            financiers = len(self.config.FINANCIERS) 
            managers = len(self.config.MANAGERS)
            
            response = f"👥 Размер команды: {data.team_size} человек"
            response += f"\n• Маркетологи: {marketers}"
            response += f"\n• Финансисты: {financiers}"
            response += f"\n• Руководители: {managers}"
            
            return response
        
        elif intent == 'weekly_payments':
            count = len(data.weekly_payments)
            total = sum(p['amount'] for p in data.weekly_payments)
            
            response = f"📈 Платежи за неделю: {count} платежей на ${total:.2f}"
            
            if count > 0:
                response += "\n\nПоследние платежи:"
                for payment in data.weekly_payments[:5]:
                    date = datetime.fromisoformat(payment['created_at']).strftime('%d.%m')
                    response += f"\n• {date}: {payment['service_name']} - ${payment['amount']:.2f}"
            
            return response
        
        elif intent == 'projects':
            if not data.projects:
                return "📋 Проекты не найдены"
            
            response = f"📋 Всего проектов: {len(data.projects)}"
            response += "\n\nТоп проекты:"
            
            for project in data.projects[:10]:
                response += f"\n• {project['project_name']}: {project['count']} платежей, ${project['total']:.2f}"
            
            return response
        
        elif intent == 'recent_operations':
            if not data.recent_operations:
                return "📋 Последние операции не найдены"
            
            response = "📋 Последние операции:"
            
            for operation in data.recent_operations[:10]:
                date = datetime.fromisoformat(operation['created_at']).strftime('%d.%m %H:%M')
                status = "✅" if operation['status'] == 'paid' else "⏳"
                response += f"\n{status} {date}: {operation['service_name']} - ${operation['amount']:.2f}"
            
            return response
        
        elif intent == 'balance_history':
            if not data.balance_history:
                return "📈 История баланса не найдена"
            
            response = "📈 История баланса:"
            
            for record in data.balance_history[:10]:
                date = datetime.fromisoformat(record['timestamp']).strftime('%d.%m %H:%M')
                amount_str = f"+${record['amount']:.2f}" if record['amount'] > 0 else f"-${abs(record['amount']):.2f}"
                response += f"\n• {date}: {amount_str} - {record['description']}"
            
            return response
        
        else:
            # Общий ответ с кратким обзором
            status = "здоровый" if data.balance >= self.config.LOW_BALANCE_THRESHOLD else "низкий"
            pending_count = len(data.pending_payments)
            pending_total = sum(p['amount'] for p in data.pending_payments)
            
            response = "📊 Общий обзор системы:"
            response += f"\n💰 Баланс: ${data.balance:.2f} ({status})"
            response += f"\n📝 Ожидающие оплаты: {pending_count} на ${pending_total:.2f}"
            response += f"\n📊 Платежи сегодня: {data.today_payments}"
            response += f"\n👥 Команда: {data.team_size} человек"
            response += f"\n📋 Проекты: {len(data.projects)}"
            
            return response


# Глобальный экземпляр помощника
manager_ai = ManagerAIAssistant()


async def process_manager_query(query: str) -> str:
    """Обработка запроса руководителя"""
    return await manager_ai.process_query(query)