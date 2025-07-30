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
        
        # Таблица проектов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица назначений проектов пользователям
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_name TEXT NOT NULL,
                assigned_by INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_name) REFERENCES projects (name),
                UNIQUE(user_id, project_name)
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
    async def get_payments_by_marketer(marketer_id: int) -> List[Dict[str, Any]]:
        """Получение всех заявок конкретного маркетолога"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM payments 
                WHERE marketer_id = ? 
                ORDER BY created_at DESC
            """, (marketer_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
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
    
    @staticmethod
    async def reject_payment(payment_id: int, reason: str = "", manager_id: int = 0):
        """Отклонение заявки на оплату"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            # Обновляем статус на rejected
            await db.execute("""
                UPDATE payments 
                SET status = 'rejected', 
                    confirmation_hash = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'pending'
            """, (reason, payment_id))
            
            affected_rows = db.total_changes
            await db.commit()
            
            if affected_rows > 0:
                logger.info(f"Заявка {payment_id} отклонена руководителем {manager_id}: {reason}")
                return True
            else:
                logger.warning(f"Заявка {payment_id} не найдена или уже обработана")
                return False
    
    @staticmethod
    async def get_payments_with_invalid_projects() -> List[Dict[str, Any]]:
        """Получение заявок с некорректными проектами"""
        config = Config()
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT p.* 
                FROM payments p
                LEFT JOIN projects pr ON p.project_name = pr.name AND pr.status = 'active'
                WHERE p.status = 'pending' 
                  AND pr.name IS NULL
                ORDER BY p.created_at DESC
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
    async def reset_balance_to_zero(description: str = "Обнуление баланса"):
        """Сброс баланса к нулю с правильной записью в историю"""
        config = Config()
        
        # Получаем текущий баланс
        current_balance = await BalanceDB.get_balance()
        
        # Если баланс уже 0, ничего не делаем
        if current_balance == 0:
            return
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            # Устанавливаем баланс в 0
            await db.execute("""
                UPDATE balance 
                SET current_balance = 0,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            
            # Записываем транзакцию
            await db.execute("""
                INSERT INTO transactions 
                (user_id, transaction_type, amount, description, payment_id)
                VALUES (?, 'reset', ?, ?, ?)
            """, (0, current_balance, description, 0))
            
            # Записываем в историю баланса операцию, которая приводит к нулю
            # Если было 400$, записываем -400$ чтобы привести к 0
            reset_amount = -current_balance
            await db.execute("""
                INSERT INTO balance_history 
                (amount, description, user_id, transaction_type)
                VALUES (?, ?, ?, ?)
            """, (reset_amount, description, 0, 'reset'))
            
            await db.commit()
            logger.info(f"Баланс сброшен к нулю (было {current_balance}$)")
    
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


class ProjectDB:
    """Класс для работы с проектами"""
    
    @staticmethod
    async def create_project(name: str, description: str = "", manager_id: int = 0) -> int:
        """Создание нового проекта"""
        config = Config()
        
        # Валидация
        if not name or not name.strip():
            raise ValueError("Название проекта не может быть пустым")
        
        name = name.strip()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            try:
                cursor = await db.execute("""
                    INSERT INTO projects (name, description, created_by)
                    VALUES (?, ?, ?)
                """, (name, description.strip(), manager_id))
                
                project_id = cursor.lastrowid
                await db.commit()
                
                logger.info(f"Создан проект: {name} (ID: {project_id})")
                return project_id
                
            except aiosqlite.IntegrityError:
                raise ValueError(f"Проект с названием '{name}' уже существует")
    
    @staticmethod
    async def get_active_projects() -> List[Dict[str, Any]]:
        """Получение списка активных проектов"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, name, description, created_at
                FROM projects 
                WHERE status = 'active'
                ORDER BY name
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    async def get_all_projects() -> List[Dict[str, Any]]:
        """Получение всех проектов"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, name, description, status, created_by, created_at
                FROM projects 
                ORDER BY created_at DESC
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    async def deactivate_project(project_name: str) -> bool:
        """Деактивация проекта"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                UPDATE projects 
                SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND status = 'active'
            """, (project_name,))
            
            affected_rows = cursor.rowcount
            await db.commit()
            
            if affected_rows > 0:
                logger.info(f"Проект деактивирован: {project_name}")
                return True
            else:
                logger.warning(f"Проект не найден или уже неактивен: {project_name}")
                return False
    
    @staticmethod
    async def activate_project(project_name: str) -> bool:
        """Активация проекта"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                UPDATE projects 
                SET status = 'active', updated_at = CURRENT_TIMESTAMP
                WHERE name = ? AND status = 'inactive'
            """, (project_name,))
            
            affected_rows = cursor.rowcount
            await db.commit()
            
            if affected_rows > 0:
                logger.info(f"Проект активирован: {project_name}")
                return True
            else:
                logger.warning(f"Проект не найден или уже активен: {project_name}")
                return False
    
    @staticmethod
    async def project_exists(project_name: str) -> bool:
        """Проверка существования активного проекта"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM projects 
                WHERE name = ? AND status = 'active'
            """, (project_name,))
            
            count = await cursor.fetchone()
            return count[0] > 0
    
    @staticmethod
    async def get_project_names() -> List[str]:
        """Получение списка названий активных проектов"""
        projects = await ProjectDB.get_active_projects()
        return [project['name'] for project in projects]


class UserProjectDB:
    """Класс для работы с назначениями проектов пользователям"""
    
    @staticmethod
    async def assign_project_to_user(user_id: int, project_name: str, manager_id: int) -> bool:
        """Назначение проекта пользователю"""
        config = Config()
        
        # Проверяем, что проект существует и активен
        if not await ProjectDB.project_exists(project_name):
            raise ValueError(f"Проект '{project_name}' не найден или неактивен")
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            try:
                await db.execute("""
                    INSERT INTO user_projects (user_id, project_name, assigned_by)
                    VALUES (?, ?, ?)
                """, (user_id, project_name, manager_id))
                
                await db.commit()
                logger.info(f"Проект '{project_name}' назначен пользователю {user_id} руководителем {manager_id}")
                return True
                
            except aiosqlite.IntegrityError:
                logger.warning(f"Проект '{project_name}' уже назначен пользователю {user_id}")
                return False
    
    @staticmethod
    async def remove_project_from_user(user_id: int, project_name: str) -> bool:
        """Отзыв проекта у пользователя"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                DELETE FROM user_projects 
                WHERE user_id = ? AND project_name = ?
            """, (user_id, project_name))
            
            affected_rows = cursor.rowcount
            await db.commit()
            
            if affected_rows > 0:
                logger.info(f"Проект '{project_name}' отозван у пользователя {user_id}")
                return True
            else:
                logger.warning(f"Проект '{project_name}' не был назначен пользователю {user_id}")
                return False
    
    @staticmethod
    async def get_user_projects(user_id: int) -> List[str]:
        """Получение списка проектов, назначенных пользователю"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT up.project_name 
                FROM user_projects up
                JOIN projects p ON up.project_name = p.name
                WHERE up.user_id = ? AND p.status = 'active'
                ORDER BY up.assigned_at DESC
            """, (user_id,))
            
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    @staticmethod
    async def get_project_users(project_name: str) -> List[int]:
        """Получение списка пользователей, которым назначен проект"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT user_id FROM user_projects 
                WHERE project_name = ?
                ORDER BY assigned_at DESC
            """, (project_name,))
            
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    @staticmethod
    async def user_has_access_to_project(user_id: int, project_name: str) -> bool:
        """Проверка, имеет ли пользователь доступ к проекту"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM user_projects up
                JOIN projects p ON up.project_name = p.name
                WHERE up.user_id = ? AND up.project_name = ? AND p.status = 'active'
            """, (user_id, project_name))
            
            count = await cursor.fetchone()
            return count[0] > 0
    
    @staticmethod
    async def get_all_user_assignments() -> List[Dict[str, Any]]:
        """Получение всех назначений проектов"""
        config = Config()
        
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT up.user_id, up.project_name, up.assigned_by, up.assigned_at,
                       p.status as project_status
                FROM user_projects up
                JOIN projects p ON up.project_name = p.name
                ORDER BY up.assigned_at DESC
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] 