"""
Веб-дашборд для руководителей
FastAPI приложение с современным интерфейсом
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timedelta
import sqlite3
import os
import sys

# Добавляем путь к родительской директории для импорта модулей бота
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from db.database import BalanceDB, PaymentDB

app = FastAPI(title="Manager Dashboard", description="Дашборд для руководителей")

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")

config = Config()


async def get_manager_auth(request: Request):
    """Проверка авторизации для руководителей"""
    client_ip = request.client.host
    
    # Разрешаем доступ только с локальных IP без токена
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return True
    
    # Для всех остальных IP - запрещаем доступ
    raise HTTPException(status_code=401, detail="Unauthorized")
    
    return True


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, auth: bool = Depends(get_manager_auth)):
    """Главная страница дашборда"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/stats")
async def get_dashboard_stats(request: Request):
    """API для получения статистики дашборда"""
    try:
        # Проверяем авторизацию
        await get_manager_auth(request)
        # Получаем базовую статистику
        current_balance = await BalanceDB.get_balance()
        pending_payments = await PaymentDB.get_pending_payments()
        
        # Вычисляем дополнительную статистику
        total_pending = sum(payment["amount"] for payment in pending_payments)
        pending_count = len(pending_payments)
        
        # Получаем историю платежей за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        recent_payments = await get_recent_payments(week_ago)
        
        # Статистика по проектам
        project_stats = await get_project_statistics()
        
        # Статистика по дням недели
        daily_stats = await get_daily_statistics()
        
        return {
            "balance": {
                "current": round(current_balance, 2),
                "threshold": config.LOW_BALANCE_THRESHOLD,
                "status": "healthy" if current_balance >= config.LOW_BALANCE_THRESHOLD else "low"
            },
            "payments": {
                "pending_count": pending_count,
                "pending_amount": round(total_pending, 2),
                "recent_payments": recent_payments,
                "completed_today": await get_payments_today()
            },
            "projects": project_stats,
            "daily": daily_stats,
            "summary": {
                "total_users": len(config.MARKETERS) + len(config.FINANCIERS) + len(config.MANAGERS),
                "marketers": len(config.MARKETERS),
                "financiers": len(config.FINANCIERS),
                "managers": len(config.MANAGERS)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


@app.get("/api/payments")
async def get_payments_data(request: Request):
    """API для получения данных о платежах"""
    try:
        # Проверяем авторизацию
        await get_manager_auth(request)
        # Получаем все платежи
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Запрос платежей с дополнительной информацией
        cursor.execute("""
            SELECT 
                id,
                service_name,
                amount,
                project_name,
                payment_method,
                status,
                created_at,
                marketer_id
            FROM payments 
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        
        payments = []
        for row in cursor.fetchall():
            payments.append({
                "id": row["id"],
                "service_name": row["service_name"],
                "amount": row["amount"],
                "project_name": row["project_name"],
                "payment_method": row["payment_method"],
                "status": row["status"],
                "created_at": row["created_at"],
                "marketer_id": row["marketer_id"]
            })
        
        conn.close()
        return {"payments": payments}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching payments: {str(e)}")


@app.get("/api/balance-history")
async def get_balance_history(request: Request):
    """API для получения истории баланса"""
    try:
        # Проверяем авторизацию
        await get_manager_auth(request)
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Получаем историю изменений баланса
        cursor.execute("""
            SELECT 
                amount,
                description,
                timestamp,
                user_id
            FROM balance_history 
            ORDER BY timestamp DESC 
            LIMIT 30
        """)
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "amount": row["amount"],
                "description": row["description"],
                "timestamp": row["timestamp"],
                "user_id": row["user_id"]
            })
        
        conn.close()
        return {"history": history}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching balance history: {str(e)}")


async def get_recent_payments(since_date):
    """Получает платежи с определенной даты"""
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM payments 
            WHERE created_at >= ? AND status = 'paid'
        """, (since_date.isoformat(),))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "count": result["count"] or 0,
            "total": round(result["total"] or 0, 2)
        }
    except:
        return {"count": 0, "total": 0}


async def get_project_statistics():
    """Получает статистику по проектам"""
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                project_name,
                COUNT(*) as count,
                SUM(amount) as total,
                AVG(amount) as avg_amount
            FROM payments 
            WHERE project_name IS NOT NULL
            GROUP BY project_name 
            ORDER BY total DESC
            LIMIT 10
        """)
        
        projects = []
        for row in cursor.fetchall():
            projects.append({
                "name": row["project_name"],
                "count": row["count"],
                "total": round(row["total"], 2),
                "average": round(row["avg_amount"], 2)
            })
        
        conn.close()
        return projects
    except:
        return []


async def get_daily_statistics():
    """Получает статистику по дням"""
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Статистика за последние 7 дней
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count,
                SUM(amount) as total
            FROM payments 
            WHERE created_at >= date('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
        
        daily = []
        for row in cursor.fetchall():
            daily.append({
                "date": row["date"],
                "count": row["count"],
                "total": round(row["total"], 2)
            })
        
        conn.close()
        return daily
    except:
        return []


async def get_payments_today():
    """Получает количество платежей за сегодня"""
    try:
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM payments 
            WHERE DATE(created_at) = DATE('now') AND status = 'paid'
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    except:
        return 0


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)