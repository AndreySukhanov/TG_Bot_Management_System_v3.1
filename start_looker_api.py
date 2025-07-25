#!/usr/bin/env python3
"""
Запуск API сервера для интеграции с Google Looker Studio
Runs on port 8001 to avoid conflicts with main dashboard
"""

import uvicorn
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Запуск Looker Studio API сервера...")
    print("📊 API будет доступен по адресу: http://localhost:8001")
    print("🔑 API Token: looker_studio_token_2025")
    print("📋 Документация: http://localhost:8001/docs")
    print("=" * 50)
    
    # Запускаем сервер
    uvicorn.run(
        "dashboard.looker_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=["dashboard"],
        log_level="info"
    )