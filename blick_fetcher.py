"""
blick_fetcher.py — Парсер DWD-станции EDDM (München-Flughafen) с сайта blick-aufs-wetter.com.

Источник:  https://www.blick-aufs-wetter.com/messwerte/ort/M%C3%BCnchen-Flughafen/01262
Данные:    DWD Wetterstation 01262, 48.3477°N 11.8134°E, 446 m üNN
Обновление: каждые 10 минут
Технология: чистый HTML-парсинг, JavaScript не нужен
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_URL = (
    "https://www.blick-aufs-wetter.com"
    "/messwerte/ort/M%C3%BCnchen-Flughafen/01262"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
    "Cache-Control": "no-cache",
}


@dataclass
class BlickData:
    """Последнее 10-минутное измерение DWD EDDM."""
    datetime_str: str = ""     # «25.05 - 21:20 Uhr»
    temp: str = ""             # «19.7» °C
    precip: str = ""           # «0.0» l/m² (за 10 мин)
    dewpoint: str = ""         # «13.7» °C
    humidity: str = ""         # «68» %
    gust: str = ""             # «8» km/h
    wind_dir: str = ""         # «320» ° (направление в градусах)
    pressure: str = ""         # «977» hPa


def _parse_html(html: str) -> Optional[BlickData]:
    """Парсит HTML страницы и возвращает последнее полное измерение."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        log.warning("Blick: таблица не найдена")
        return None

    rows = table.find_all("tr")[1:]  # пропускаем заголовок
    if not rows:
        log.warning("Blick: таблица пуста")
        return None

    # Ищем первую строку, где есть температура (не прочерк)
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 7:
            continue

        dt_str, temp, precip, tdew, rh, gust, wdir = cells[:7]
        pressure = cells[7] if len(cells) > 7 else ""

        # Пропускаем строки где температура — прочерк
        if temp in ("-", "", "–"):
            continue

        return BlickData(
            datetime_str=dt_str,
            temp=temp,
            precip=precip,
            dewpoint=tdew,
            humidity=rh,
            gust=gust,
            wind_dir=wdir,
            pressure=pressure if pressure not in ("-", "") else "",
        )

    log.warning("Blick: ни одна строка не содержит температуру")
    return None


def _fetch_sync() -> Optional[BlickData]:
    """Синхронный HTTP-запрос + парсинг."""
    try:
        with httpx.Client(timeout=15.0, headers=_HEADERS, follow_redirects=True) as c:
            r = c.get(_URL)
            if r.status_code != 200:
                log.warning(f"Blick: HTTP {r.status_code}")
                return None
            return _parse_html(r.text)
    except httpx.RequestError as e:
        log.warning(f"Blick: сетевая ошибка: {e}")
    except Exception as e:
        log.error(f"Blick: неожиданная ошибка: {e}", exc_info=True)
    return None


async def fetch_blick() -> Optional[BlickData]:
    """Async-обёртка (запускается в отдельном потоке)."""
    return await asyncio.to_thread(_fetch_sync)
