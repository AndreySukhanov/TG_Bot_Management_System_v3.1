"""
Модуль для работы с базой данных.
Создает таблицы и предоставляет интерфейс для работы с данными.
"""

import os
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from utils.config import Config

logger = logging.getLogger(__name__)


async def init_database():
    """Инициализация базы данных и создание таблиц"""
    config = Config()
    
    # Создание директории для базы данных
    db_dir = os.path.dirname(config.DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        # Таблица платежей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marketer_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                payment_method TEXT NOT NULL,
                payment_details TEXT,
                project_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                confirmation_hash TEXT,
                confirmation_file TEXT
            )
        """)
        
        # Таблица транзакций баланса
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payment_id INTEGER,
                FOREIGN KEY (payment_id) REFERENCES payments (id)
            )
        """)
        
        # Таблица баланса
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance (
                id INTEGER PRIMARY KEY,
                current_balance REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_low_balance_alert TIMESTAMP
            )
        """)
        
        # Таблица истории баланса
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                transaction_type TEXT
            )
        """)
        
        # Проверяем, есть ли запись в balance, если нет - создаем
        cursor = await db.execute("SELECT COUNT(*) FROM balance")
        count = await cursor.fetchone()
        if count[0] == 0:
            await db.execute("""
                INSERT INTO balance (id, current_balance) VALUES (1, 0.0)
            """)
        
        await db.commit()
        logger.info("База данных инициализирована успешно")


class PaymentDB:
    """Класс для работы с платежами"""
    
    @staticmethod
    async def create_payment(marketer_id: int, service_name: str, amount: float, 
                           payment_method: str, payment_details: str, 
                           project_name: str, file_path: Optional[str] = None) -> int:
        """Создание новой заявки на платеж"""
        config = Config()
        
        # Валидация входных данных
        if amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")
        if not service_name.strip():
            raise ValueError("Название сервиса не может быть пустым")
        if not project_name.strip():
            raise ValueError("Название проекта не может быть пустым")
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                INSERT INTO payments 
                (marketer_id, service_name, amount, payment_method, 
                 payment_details, project_name, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (marketer_id, service_name, amount, payment_method, 
                  payment_details, project_name, file_path))
            
            payment_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Создана заявка на платеж ID: {payment_id}")
            return payment_id
    
    @staticmethod
    async def get_payment(payment_id: int) -> Optional[Dict[str, Any]]:
        """Получение платежа по ID"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM payments WHERE id = ?
            """, (payment_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    async def update_payment_status(payment_id: int, status: str, 
                                  confirmation_hash: Optional[str] = None,
                                  confirmation_file: Optional[str] = None):
        """Обновление статуса платежа"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("""
                UPDATE payments 
                SET status = ?, confirmation_hash = ?, confirmation_file = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, confirmation_hash, confirmation_file, payment_id))
            
            await db.commit()
            logger.info(f"Обновлен статус платежа ID: {payment_id} -> {status}")
    
    @staticmethod
    async def get_pending_payments() -> List[Dict[str, Any]]:
        """Получение всех ожидающих платежей"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM payments WHERE status = 'pending'
                ORDER BY created_at DESC
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class BalanceDB:
    """Класс для работы с балансом"""
    
    @staticmethod
    async def get_balance() -> float:
        """Получение текущего баланса"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT current_balance FROM balance WHERE id = 1
            """)
            
            row = await cursor.fetchone()
            return row[0] if row else 0.0
    
    @staticmethod
    async def add_balance(amount: float, user_id: int, description: str = ""):
        """Пополнение баланса"""
        config = Config()
        
        # Валидация входных данных
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть больше нуля")
        if user_id <= 0:
            raise ValueError("ID пользователя некорректен")
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            # Обновляем баланс
            await db.execute("""
                UPDATE balance 
                SET current_balance = current_balance + ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (amount,))
            
            # Записываем транзакцию
            await db.execute("""
                INSERT INTO transactions 
                (user_id, transaction_type, amount, description)
                VALUES (?, 'income', ?, ?)
            """, (user_id, amount, description))
            
            # Записываем в историю баланса
            await db.execute("""
                INSERT INTO balance_history 
                (amount, description, user_id, transaction_type)
                VALUES (?, ?, ?, ?)
            """, (amount, description or f"Пополнение баланса", user_id, 'income'))
            
            await db.commit()
            logger.info(f"Баланс пополнен на {amount}$")
    
    @staticmethod
    async def subtract_balance(amount: float, payment_id: int, description: str = ""):
        """Списание с баланса"""
        config = Config()
        
        # Валидация входных данных
        if amount <= 0:
            raise ValueError("Сумма списания должна быть больше нуля")
        if payment_id < 0:
            raise ValueError("ID платежа некорректен")
        
        # Проверка достаточности средств
        current_balance = await BalanceDB.get_balance()
        if current_balance < amount:
            logger.warning(f"Недостаточно средств для списания {amount}$. Текущий баланс: {current_balance}$")
            # Не блокируем операцию, но логируем предупреждение
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            # Обновляем баланс
            await db.execute("""
                UPDATE balance 
                SET current_balance = current_balance - ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (amount,))
            
            # Записываем транзакцию
            await db.execute("""
                INSERT INTO transactions 
                (user_id, transaction_type, amount, description, payment_id)
                VALUES (?, 'expense', ?, ?, ?)
            """, (0, amount, description, payment_id))
            
            # Записываем в историю баланса
            await db.execute("""
                INSERT INTO balance_history 
                (amount, description, user_id, transaction_type)
                VALUES (?, ?, ?, ?)
            """, (-amount, description or f"Списание с баланса", 0, 'expense'))
            
            await db.commit()
            logger.info(f"С баланса списано {amount}$")
    
    @staticmethod
    async def check_low_balance() -> bool:
        """Проверка на низкий баланс"""
        config = Config()
        current_balance = await BalanceDB.get_balance()
        return current_balance < config.LOW_BALANCE_THRESHOLD
    
    @staticmethod
    async def update_low_balance_alert():
        """Обновление времени последнего уведомления о низком балансе"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("""
                UPDATE balance 
                SET last_low_balance_alert = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            await db.commit()
    
    @staticmethod
    async def should_send_low_balance_alert() -> bool:
        """Проверка, нужно ли отправлять уведомление о низком балансе"""
        config = Config()
        
        if not await BalanceDB.check_low_balance():
            return False
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT last_low_balance_alert FROM balance WHERE id = 1
            """)
            
            row = await cursor.fetchone()
            if not row or not row[0]:
                return True
            
            # Проверяем, не отправляли ли уведомление недавно
            last_alert = datetime.fromisoformat(row[0])
            current_balance = await BalanceDB.get_balance()
            
            # Отправляем уведомление только если баланс стал еще ниже
            cursor = await db.execute("""
                SELECT COUNT(*) FROM transactions 
                WHERE created_at > ? AND transaction_type = 'expense'
            """, (last_alert.isoformat(),))
            
            expense_count = await cursor.fetchone()
            return expense_count[0] > 0 