"""
run_icon_d2.py — Запуск только ICON D2 сканера (без METAR-сканеров).

При запуске сразу отправляет текущий прогноз EDDM, затем обновляется
каждые 3 часа по мере выхода новых расчётов DWD ICON D2.
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
from bot import icon_d2_loop, _icon_configs


async def main():
    icon_configs = _icon_configs()
    if not icon_configs:
        print("❌ Укажите хотя бы один forecast в config.ICON_FORECASTS и запустите снова.")
        return

    _request = HTTPXRequest(connection_pool_size=8, pool_timeout=15.0)
    bot = Bot(token=cfg.BOT_TOKEN, request=_request)
    try:
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username} ({me.full_name})")
        print(f"   Прогнозов: {len(icon_configs)}")
        for icon_cfg in icon_configs:
            print(f"   {icon_cfg.icao}: {icon_cfg.model} -> {icon_cfg.chat_ids}")
        print("   Запуски: 00, 03, 06, 09, 12, 15, 18, 21 UTC (данные ~через 75 мин)")
        print("   Запуск ICON сканера...\n")
    except TelegramError as e:
        print(f"❌ Ошибка авторизации бота: {e}")
        return

    await icon_d2_loop(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nICON D2 сканер остановлен")
