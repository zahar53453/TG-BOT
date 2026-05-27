"""run_lfpb.py — Запуск только сканера Париж Ле-Бурже."""
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main(["LFPB"]))
    except KeyboardInterrupt:
        print("\nСканер LFPB остановлен")
