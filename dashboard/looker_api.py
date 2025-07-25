"""
API эндпоинты для интеграции с Google Looker Studio
Предоставляет данные в формате, оптимизированном для Looker Studio
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional, List
import sqlite3
import os
import sys

# Добавляем путь к родительской директории для импорта модулей бота
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from db.database import BalanceDB, PaymentDB

app = FastAPI(
    title="Looker Studio API",
    description="API для интеграции с Google Looker Studio",
    version="1.0.0"
)

# Настройка CORS для Looker Studio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lookerstudio.google.com", "https://datastudio.google.com"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

config = Config()
security = HTTPBearer()

# Простая авторизация по токену для Looker Studio
LOOKER_API_TOKEN = "looker_studio_token_2025"  # Можно вынести в .env


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена для доступа к API"""
    if credentials.credentials != LOOKER_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return credentials.credentials


@app.get("/")
async def root():
    """Корневой эндпоинт с информацией об API"""
    return {
        "service": "Looker Studio API",
        "version": "1.0.0",
        "description": "API для интеграции Telegram бота с Google Looker Studio",
        "endpoints": [
            "/payments - данные о платежах",
            "/balance-history - история изменений баланса", 
            "/projects - статистика по проектам",
            "/daily-stats - ежедневная статистика",
            "/users - информация о пользователях"
        ]
    }


@app.get("/payments")
async def get_payments_for_looker(
    token: str = Depends(verify_token),
    days: Optional[int] = Query(30, description="Количество дней для выборки"),
    status: Optional[str] = Query(None, description="Фильтр по статусу (pending, paid)")
):
    """
    Получить данные о платежах для Looker Studio
    
    Возвращает структурированные данные о всех платежах с возможностью фильтрации
    """
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Базовый запрос
        query = """
            SELECT 
                id,
                service_name,
                amount,
                project_name,
                payment_method,
                payment_details,
                status,
                created_at,
                updated_at,
                marketer_id,
                DATE(created_at) as payment_date,
                strftime('%Y-%m', created_at) as payment_month,
                strftime('%Y-%W', created_at) as payment_week,
                strftime('%w', created_at) as day_of_week,
                strftime('%H', created_at) as hour_of_day
            FROM payments 
            WHERE created_at >= date('now', '-{} days')
        """.format(days)
        
        # Добавляем фильтр по статусу если указан
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
            
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        
        payments = []
        for row in cursor.fetchall():
            # Определяем тип пользователя по ID
            user_type = "unknown"
            if row["marketer_id"] in config.MARKETERS:
                user_type = "marketer"
            elif row["marketer_id"] in config.FINANCIERS:
                user_type = "financier"
            elif row["marketer_id"] in config.MANAGERS:
                user_type = "manager"
                
            payments.append({
                "payment_id": row["id"],
                "service_name": row["service_name"],
                "amount": float(row["amount"]),
                "project_name": row["project_name"],
                "payment_method": row["payment_method"],
                "payment_details": row["payment_details"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "marketer_id": row["marketer_id"],
                "user_type": user_type,
                "payment_date": row["payment_date"],
                "payment_month": row["payment_month"],
                "payment_week": row["payment_week"],
                "day_of_week": int(row["day_of_week"]),
                "hour_of_day": int(row["hour_of_day"]),
                "is_weekend": int(row["day_of_week"]) in [0, 6],  # Воскресенье = 0, Суббота = 6
                "amount_usd": float(row["amount"]),  # Дублируем для удобства в Looker
                "status_numeric": 1 if row["status"] == "paid" else 0  # Для числовых фильтров
            })
        
        conn.close()
        
        return {
            "data": payments,
            "meta": {
                "total_records": len(payments),
                "date_range_days": days,
                "generated_at": datetime.now().isoformat(),
                "status_filter": status
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching payments: {str(e)}")


@app.get("/balance-history")
async def get_balance_history_for_looker(
    token: str = Depends(verify_token),
    days: Optional[int] = Query(90, description="Количество дней для выборки")
):
    """
    Получить историю изменений баланса для Looker Studio
    """
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                amount,
                description,
                timestamp,
                user_id,
                payment_id,
                DATE(timestamp) as operation_date,
                strftime('%Y-%m', timestamp) as operation_month,
                strftime('%Y-%W', timestamp) as operation_week
            FROM balance_history 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
        """.format(days))
        
        history = []
        running_balance = await BalanceDB.get_balance()  # Текущий баланс
        
        for i, row in enumerate(cursor.fetchall()):
            # Определяем тип операции
            operation_type = "unknown"
            if row["amount"] > 0:
                operation_type = "deposit" if row["payment_id"] == 0 else "refund"
            else:
                operation_type = "payment" if row["payment_id"] > 0 else "withdrawal"
                
            # Определяем тип пользователя
            user_type = "unknown"
            if row["user_id"]:
                if row["user_id"] in config.MARKETERS:
                    user_type = "marketer"
                elif row["user_id"] in config.FINANCIERS:
                    user_type = "financier"
                elif row["user_id"] in config.MANAGERS:
                    user_type = "manager"
            
            # Вычисляем баланс на момент операции (идем от текущего назад)
            if i == 0:
                balance_after = running_balance
            else:
                # Для предыдущих записей вычитаем/прибавляем операции
                balance_after = running_balance
                for j in range(i):
                    prev_row = cursor.fetchall()[j] if j < len(cursor.fetchall()) else None
                    if prev_row:
                        balance_after -= prev_row["amount"]
                        
            balance_before = balance_after - row["amount"]
            
            history.append({
                "operation_id": row["id"],
                "amount": float(row["amount"]),
                "amount_abs": abs(float(row["amount"])),
                "description": row["description"],
                "timestamp": row["timestamp"],
                "user_id": row["user_id"],
                "payment_id": row["payment_id"],
                "user_type": user_type,
                "operation_type": operation_type,
                "operation_date": row["operation_date"],
                "operation_month": row["operation_month"],
                "operation_week": row["operation_week"],
                "balance_before": float(balance_before),
                "balance_after": float(balance_after),
                "is_positive": row["amount"] > 0,
                "is_payment_related": row["payment_id"] > 0
            })
        
        conn.close()
        
        return {
            "data": history,
            "meta": {
                "total_records": len(history),
                "current_balance": float(await BalanceDB.get_balance()),
                "date_range_days": days,
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching balance history: {str(e)}")


@app.get("/projects")
async def get_projects_for_looker(
    token: str = Depends(verify_token),
    days: Optional[int] = Query(90, description="Количество дней для выборки")
):
    """
    Получить статистику по проектам для Looker Studio
    """
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                project_name,
                COUNT(*) as total_payments,
                COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_payments,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_payments,
                SUM(amount) as total_amount,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount,
                SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount,
                AVG(amount) as avg_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount,
                MIN(created_at) as first_payment,
                MAX(created_at) as last_payment,
                COUNT(DISTINCT marketer_id) as unique_marketers
            FROM payments 
            WHERE created_at >= date('now', '-{} days')
            AND project_name IS NOT NULL
            GROUP BY project_name 
            ORDER BY total_amount DESC
        """.format(days))
        
        projects = []
        for row in cursor.fetchall():
            # Вычисляем дополнительные метрики
            success_rate = (row["paid_payments"] / row["total_payments"]) * 100 if row["total_payments"] > 0 else 0
            days_active = (datetime.now() - datetime.fromisoformat(row["first_payment"])).days + 1
            avg_payments_per_day = row["total_payments"] / days_active if days_active > 0 else 0
            
            projects.append({
                "project_name": row["project_name"],
                "total_payments": row["total_payments"],
                "paid_payments": row["paid_payments"],
                "pending_payments": row["pending_payments"],
                "total_amount": float(row["total_amount"]),
                "paid_amount": float(row["paid_amount"]),
                "pending_amount": float(row["pending_amount"]),
                "avg_amount": float(row["avg_amount"]),
                "min_amount": float(row["min_amount"]),
                "max_amount": float(row["max_amount"]),
                "first_payment": row["first_payment"],
                "last_payment": row["last_payment"],
                "unique_marketers": row["unique_marketers"],
                "success_rate": round(success_rate, 2),
                "days_active": days_active,
                "avg_payments_per_day": round(avg_payments_per_day, 2),
                "is_active": (datetime.now() - datetime.fromisoformat(row["last_payment"])).days <= 7
            })
        
        conn.close()
        
        return {
            "data": projects,
            "meta": {
                "total_projects": len(projects),
                "date_range_days": days,
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching projects: {str(e)}")


@app.get("/daily-stats")
async def get_daily_stats_for_looker(
    token: str = Depends(verify_token),
    days: Optional[int] = Query(30, description="Количество дней для выборки")
):
    """
    Получить ежедневную статистику для Looker Studio
    """
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_payments,
                COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_payments,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_payments,
                SUM(amount) as total_amount,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount,
                AVG(amount) as avg_amount,
                COUNT(DISTINCT project_name) as unique_projects,
                COUNT(DISTINCT marketer_id) as unique_marketers,
                strftime('%w', created_at) as day_of_week,
                strftime('%Y-%m', created_at) as month,
                strftime('%Y-%W', created_at) as week
            FROM payments 
            WHERE created_at >= date('now', '-{} days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """.format(days))
        
        daily_stats = []
        for row in cursor.fetchall():
            day_names = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
            day_of_week_num = int(row["day_of_week"])
            
            daily_stats.append({
                "date": row["date"],
                "total_payments": row["total_payments"],
                "paid_payments": row["paid_payments"],
                "pending_payments": row["pending_payments"],
                "total_amount": float(row["total_amount"]),
                "paid_amount": float(row["paid_amount"]),
                "avg_amount": float(row["avg_amount"]) if row["avg_amount"] else 0,
                "unique_projects": row["unique_projects"],
                "unique_marketers": row["unique_marketers"],
                "day_of_week": day_of_week_num,
                "day_name": day_names[day_of_week_num],
                "month": row["month"],
                "week": row["week"],
                "is_weekend": day_of_week_num in [0, 6],
                "success_rate": (row["paid_payments"] / row["total_payments"]) * 100 if row["total_payments"] > 0 else 0
            })
        
        conn.close()
        
        return {
            "data": daily_stats,
            "meta": {
                "total_days": len(daily_stats),
                "date_range_days": days,
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching daily stats: {str(e)}")


@app.get("/users")
async def get_users_for_looker(token: str = Depends(verify_token)):
    """
    Получить информацию о пользователях системы для Looker Studio
    """
    try:
        users_data = []
        
        # Маркетологи
        for user_id in config.MARKETERS:
            # Получаем статистику по каждому маркетологу
            db_path = config.DATABASE_PATH
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_payments,
                    COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_payments,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount,
                    MIN(created_at) as first_payment,
                    MAX(created_at) as last_payment
                FROM payments 
                WHERE marketer_id = ?
            """, (user_id,))
            
            stats = cursor.fetchone()
            conn.close()
            
            users_data.append({
                "user_id": user_id,
                "user_type": "marketer",
                "total_payments": stats[0] if stats[0] else 0,
                "paid_payments": stats[1] if stats[1] else 0,
                "total_amount": float(stats[2]) if stats[2] else 0.0,
                "avg_amount": float(stats[3]) if stats[3] else 0.0,
                "first_payment": stats[4],
                "last_payment": stats[5],
                "is_active": bool(stats[0])  # Есть ли платежи
            })
        
        # Финансисты
        for user_id in config.FINANCIERS:
            users_data.append({
                "user_id": user_id,
                "user_type": "financier",
                "total_payments": 0,
                "paid_payments": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "first_payment": None,
                "last_payment": None,
                "is_active": True  # Считаем финансистов всегда активными
            })
        
        # Руководители
        for user_id in config.MANAGERS:
            users_data.append({
                "user_id": user_id,
                "user_type": "manager",
                "total_payments": 0,
                "paid_payments": 0,
                "total_amount": 0.0,
                "avg_amount": 0.0,
                "first_payment": None,
                "last_payment": None,
                "is_active": True  # Считаем руководителей всегда активными
            })
        
        return {
            "data": users_data,
            "meta": {
                "total_users": len(users_data),
                "marketers": len(config.MARKETERS),
                "financiers": len(config.FINANCIERS),
                "managers": len(config.MANAGERS),
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Другой порт, чтобы не конфликтовать с основным дашбордом