"""
run_all.py — Запуск всех 4 сканеров в одном процессе.

Каждый сканер работает в своём параллельном asyncio-потоке:
  • EGLC → свой Telegram-чат
  • LFPB → свой Telegram-чат
  • LEMD → свой Telegram-чат
  • EDDM → свой Telegram-чат
"""
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())   # None = все сканеры из config.SCANNERS
    except KeyboardInterrupt:
        print("\nВсе сканеры остановлены")
