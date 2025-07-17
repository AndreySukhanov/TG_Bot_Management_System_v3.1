#!/usr/bin/env python3
"""
Точка входа для запуска Telegram-бота.
Импортирует и запускает основную функцию из bot.py
"""

if __name__ == "__main__":
    from bot import main
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
