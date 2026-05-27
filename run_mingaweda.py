"""
run_mingaweda.py — Запуск только MingaWeda-сканера (без METAR-сканеров).

Используйте, если хотите запустить парсер погоды München отдельно.
Не забудьте указать chat_ids в config.MINGAWEDA.
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
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
from bot import mingaweda_loop


async def main():
    if not cfg.MINGAWEDA.get("chat_ids"):
        print("❌ Укажите chat_ids в config.MINGAWEDA и запустите снова.")
        return

    _request = HTTPXRequest(connection_pool_size=8, pool_timeout=15.0)
    bot = Bot(token=cfg.BOT_TOKEN, request=_request)
    try:
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username} ({me.full_name})")
        print(f"   Чаты: {cfg.MINGAWEDA['chat_ids']}")
        print(f"   Интервал: {cfg.MINGAWEDA_POLL_INTERVAL} сек")
        print("   Запуск MingaWeda-сканера...\n")
    except TelegramError as e:
        print(f"❌ Ошибка авторизации бота: {e}")
        return

    await mingaweda_loop(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMingaWeda-сканер остановлен")
