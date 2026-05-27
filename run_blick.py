"""
run_blick.py — Запуск только Blick-сканера (без METAR-сканеров).

Парсит DWD Wetterstation EDDM (München-Flughafen) каждые 10 минут.
Источник: https://www.blick-aufs-wetter.com/messwerte/ort/München-Flughafen/01262
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

from telegram import Bot
from telegram.error import TelegramError
from telegram.request import HTTPXRequest
import config as cfg
from bot import blick_loop


async def main():
    if not cfg.BLICK.get("chat_ids"):
        print("❌ Укажите chat_ids в config.BLICK и запустите снова.")
        return

    _request = HTTPXRequest(connection_pool_size=8, pool_timeout=15.0)
    bot = Bot(token=cfg.BOT_TOKEN, request=_request)
    try:
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username} ({me.full_name})")
        print(f"   Чаты:     {cfg.BLICK['chat_ids']}")
        print(f"   Интервал: {cfg.BLICK_POLL_INTERVAL} сек (каждые 10 минут)")
        print(f"   Источник: blick-aufs-wetter.com · DWD EDDM")
        print("   Запуск Blick-сканера...\n")
    except TelegramError as e:
        print(f"❌ Ошибка авторизации бота: {e}")
        return

    await blick_loop(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBlick-сканер остановлен")
