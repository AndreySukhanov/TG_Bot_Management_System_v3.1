"""
Запуск веб-дашборда для руководителей
"""

import asyncio
import uvicorn
import sys
import os

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Инициализация базы данных
from db.database import init_database

async def main():
    """Основная функция запуска"""
    print("Инициализация базы данных...")
    await init_database()
    print("База данных инициализирована успешно!")
    
    print("Запуск дашборда...")
    print("Дашборд будет доступен по адресу: http://localhost:8000")
    print("Для доступа используйте токен: demo_token")
    print("Добавьте параметр ?token=demo_token к URL или заголовок Authorization: demo_token")
    
    # Запуск веб-сервера
    uvicorn.run(
        "dashboard.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    asyncio.run(main())