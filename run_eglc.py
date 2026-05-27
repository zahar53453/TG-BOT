"""run_eglc.py — Запуск только сканера Лондон Сити."""
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main(["EGLC"]))
    except KeyboardInterrupt:
        print("\nСканер EGLC остановлен")
