"""
mingaweda_fetcher.py — Парсер погодной станции MingaWeda (Мюнхен).

Источник: https://www.mingaweda.de/
Обновление данных на сайте: каждую минуту.
Парсинг: чистый HTML, без JS, без API-ключей.
Кодировка сайта: ISO-8859-1.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_URL = "https://www.mingaweda.de/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}


@dataclass
class MingaWedaData:
    """Набор погодных параметров, распарсенных с главной страницы сайта."""
    timestamp: str = ""          # «Montag, dem 25.5.2026, um 15:24 Uhr»

    temp: str = ""               # «28.5 °C»
    temp_trend: str = ""         # «steigend» / «fallend» / «konstant»
    temp_feels: str = ""         # «33.5 °C» (ощущаемая)

    pressure: str = ""           # «1030 hPa (NN)»
    pressure_trend: str = ""     # «steigend» / «fallend» / «konstant»

    wind_speed: str = ""         # «5 km/h»
    wind_dir: str = ""           # «Nord-Nord-Ost (22°)»
    wind_bft: str = ""           # «1 Bft»
    gust_speed: str = ""         # «16 km/h»
    gust_bft: str = ""           # «3 Bft»

    rain: str = ""               # «kein Regen» / «seit X min» / «X mm»

    humidity_rel: str = ""       # «37 % rF»
    humidity_abs: str = ""       # «10.2 g/m³»
    humidity_label: str = ""     # «feucht» / «schwül» / «trocken»

    clouds: str = ""             # «2/8 = heiter»


def _parse_html(html: str) -> Optional[MingaWedaData]:
    """Разбирает HTML главной страницы и возвращает MingaWedaData или None."""
    soup = BeautifulSoup(html, "html.parser")
    d = MingaWedaData()

    # ── Время/дата из заголовка ───────────────────────────────────────────────
    h3 = soup.find("h3")
    if h3:
        d.timestamp = h3.get_text(strip=True)

    # ── Обходим таблицу с данными, строка за строкой ──────────────────────────
    for row in soup.find_all("tr"):
        h2 = row.find("h2")
        if not h2:
            continue

        label = h2.get_text(strip=True).rstrip(":").lower()
        werte_td = row.find(class_="Werte")
        zusatz_td = row.find(class_="Zusatz")

        werte  = werte_td.get_text(" ", strip=True) if werte_td else ""
        zusatz = zusatz_td.get_text(" ", strip=True) if zusatz_td else ""

        # Определяем тенденцию по img alt= (konstant/steigend/fallend)
        trend = ""
        if werte_td or zusatz_td:
            for parent in [werte_td, zusatz_td]:
                if parent:
                    img = parent.find("img")
                    if img and img.get("alt"):
                        trend = img["alt"]
                        break
            # Fallback: текстовый поиск в zusatz
            if not trend:
                for kw in ("steigend", "fallend", "konstant"):
                    if kw in zusatz.lower():
                        trend = kw
                        break

        if "temperatur" in label:
            d.temp = werte
            d.temp_trend = trend
            # Ощущаемая температура: «gefühlt ca. 33.5 °C»
            import re
            m = re.search(r"gef[^\d]+([\d,\.]+\s*°C)", zusatz)
            if m:
                d.temp_feels = m.group(1)
            else:
                # иногда просто «ca. 33.5 °C»
                m2 = re.search(r"([\d,\.]+\s*°C)", zusatz)
                d.temp_feels = m2.group(1) if m2 else zusatz

        elif "luftdruck" in label:
            d.pressure = werte
            d.pressure_trend = trend

        elif "wind" in label and "böen" not in label and "boen" not in label:
            d.wind_speed = werte
            # zusatz: «= 1 Bft aus Nord-Nord-Ost (22°)»
            import re
            m = re.search(r"(\d+)\s*Bft\s+aus\s+(.+)", zusatz)
            if m:
                d.wind_bft = m.group(1) + " Bft"
                d.wind_dir = m.group(2).strip()
            else:
                # иногда направление уже в werte
                d.wind_dir = zusatz

        elif "böen" in label or "boen" in label:
            d.gust_speed = werte
            import re
            m = re.search(r"(\d+)\s*Bft", zusatz)
            d.gust_bft = m.group(1) + " Bft" if m else zusatz

        elif "regen" in label or "seit" in label:
            d.rain = werte

        elif "luftfeuchtigkeit" in label:
            d.humidity_rel = werte
            # zusatz: «= 10.2 g/m³ (absolut) = feucht»
            import re
            m = re.search(r"([\d,\.]+\s*g/m[²³3])", zusatz)
            if m:
                d.humidity_abs = m.group(1)
            for kw in ("trocken", "normal", "feucht", "schwül", "sehr schwül"):
                if kw in zusatz.lower():
                    d.humidity_label = kw
                    break

        elif "wolken" in label or "dunst" in label:
            d.clouds = werte + (" " + zusatz if zusatz else "")

    # Проверка — получили хоть что-то?
    if not d.temp and not d.pressure:
        log.warning("MingaWeda: данные не найдены в HTML")
        return None

    return d


def _fetch_sync() -> Optional[MingaWedaData]:
    """Синхронный HTTP-запрос + парсинг."""
    try:
        with httpx.Client(timeout=15.0, headers=_HEADERS, follow_redirects=True) as c:
            r = c.get(_URL)
            if r.status_code != 200:
                log.warning(f"MingaWeda: HTTP {r.status_code}")
                return None
            # Сайт отдаёт ISO-8859-1, httpx может неправильно определить кодировку
            html = r.content.decode("iso-8859-1")
            return _parse_html(html)
    except httpx.RequestError as e:
        log.warning(f"MingaWeda: сетевая ошибка: {e}")
    except Exception as e:
        log.error(f"MingaWeda: неожиданная ошибка: {e}", exc_info=True)
    return None


async def fetch_mingaweda() -> Optional[MingaWedaData]:
    """Async-обёртка над синхронным парсером (запускается в отдельном потоке)."""
    return await asyncio.to_thread(_fetch_sync)
