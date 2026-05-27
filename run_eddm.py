"""run_eddm.py — Запуск только сканера Мюнхен."""
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main(["EDDM"]))
    except KeyboardInterrupt:
        print("\nСканер EDDM остановлен")
