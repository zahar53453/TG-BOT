"""run_lemd.py — Запуск только сканера Мадрид Барахас."""
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main(["LEMD"]))
    except KeyboardInterrupt:
        print("\nСканер LEMD остановлен")
