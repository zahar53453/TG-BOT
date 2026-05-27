"""
mingaweda_formatter.py — Форматирование погодных данных MingaWeda для Telegram.
Все подписи и переводы значений — на русском языке.
"""

import re
from mingaweda_fetcher import MingaWedaData

# ── Тенденции ─────────────────────────────────────────────────────────────────
_TREND_RU = {
    "steigend":          "↗️ растёт",
    "schnell steigend":  "↑↑ быстро растёт",
    "langsam steigend":  "↗️ медленно растёт",
    "fallend":           "↘️ падает",
    "schnell fallend":   "↓↓ быстро падает",
    "langsam fallend":   "↘️ медленно падает",
    "konstant":          "→ стабильно",
    "":                  "",
}


# ── Влажность ─────────────────────────────────────────────────────────────────
_HUMIDITY_RU = {
    "trocken":     "🏜️ сухо",
    "normal":      "✅ норма",
    "feucht":      "💧 влажно",
    "schwül":      "🥵 душно",
    "sehr schwül": "🥵🥵 очень душно",
}

# ── Осадки ────────────────────────────────────────────────────────────────────
_RAIN_RU = {
    "kein regen":  "дождя нет",
    "kein schnee": "снега нет",
    "kein niederschlag": "осадков нет",
}

# ── Облачность ────────────────────────────────────────────────────────────────
_CLOUD_RU = {
    "wolkenlos":       "0/8 — ясно",
    "heiter":          "малооблачно",
    "leicht bewölkt":  "слабая облачность",
    "wolkig":          "переменная облачность",
    "bewölkt":         "облачно",
    "stark bewölkt":   "сильная облачность",
    "fast bedeckt":    "почти пасмурно",
    "bedeckt":         "пасмурно",
    "dunst":           "дымка",
    "nebel":           "туман",
}

# ── Стороны света (немецкие → русские) ───────────────────────────────────────
_DIR_RU = {
    "nord":          "С",
    "süd":           "Ю",
    "ost":           "В",
    "west":          "З",
    "nord-ost":      "СВ",
    "nord-west":     "СЗ",
    "süd-ost":       "ЮВ",
    "süd-west":      "ЮЗ",
    "nord-nord-ost": "ССВ",
    "nord-nord-west":"ССЗ",
    "süd-süd-ost":   "ЮЮВ",
    "süd-süd-west":  "ЮЮЗ",
    "ost-nord-ost":  "ВСВ",
    "ost-süd-ost":   "ВЮВ",
    "west-nord-west":"ЗСЗ",
    "west-süd-west": "ЗЮЗ",
}


def _trend(key: str) -> str:
    k = key.lower().strip()
    # Сначала ищем точное совпадение
    if k in _TREND_RU:
        return _TREND_RU[k]
    # Затем ищем по наибольшему совпадению подстроки (для составных фраз)
    best_len, best_val = 0, k
    for de, ru in _TREND_RU.items():
        if de and de in k and len(de) > best_len:
            best_len, best_val = len(de), ru
    return best_val



def _rain_ru(text: str) -> str:
    """Переводит строку об осадках с немецкого на русский."""
    low = text.lower().strip()
    for de, ru in _RAIN_RU.items():
        if de in low:
            return ru
    # «seit X Minuten kein Regen» → «дождя нет уже X мин»
    m = re.search(r"seit\s+(\d+)\s+tag", low)
    if m:
        days = int(m.group(1))
        return f"дождя нет уже {days} {'день' if days == 1 else 'дн.'}"
    m = re.search(r"seit\s+(\d+)\s+stunde", low)
    if m:
        h = int(m.group(1))
        return f"дождя нет уже {h} ч"
    m = re.search(r"seit\s+(\d+)\s+minute", low)
    if m:
        mins = int(m.group(1))
        return f"дождя нет уже {mins} мин"
    # Количество осадков: «X,X mm»
    m = re.search(r"([\d,\.]+)\s*mm", text)
    if m:
        return f"осадки: {m.group(1).replace(',', '.')} мм"
    return text  # оставляем как есть, если не распознали


def _clouds_ru(text: str) -> str:
    """Переводит строку об облачности."""
    low = text.lower()
    # Ищем дробь «N/8» и текстовое описание
    fraction = ""
    m = re.search(r"(\d/8)", text)
    if m:
        fraction = m.group(1)

    # Подбираем русский вариант
    for de, ru in _CLOUD_RU.items():
        if de in low:
            return f"{fraction} — {ru}" if fraction else ru

    return text


def _dir_ru(text: str) -> str:
    """Переводит направление ветра: «Nord-Ost (45°)» → «СВ (45°)»."""
    # Извлекаем градусы
    deg = ""
    m = re.search(r"\((\d+)°\)", text)
    if m:
        deg = f" ({m.group(1)}°)"

    # Убираем градусы для поиска направления
    direction = re.sub(r"\s*\(\d+°\)", "", text).strip().lower()
    ru = _DIR_RU.get(direction)
    if ru:
        return ru + deg

    # Fallback: ищем частичное совпадение (longest match)
    best = ""
    for de, ru in sorted(_DIR_RU.items(), key=lambda x: -len(x[0])):
        if de in direction:
            best = ru
            break
    return (best + deg) if best else text


def _bft_ru(bft_str: str) -> str:
    """«3 Bft» → «3 Бф»"""
    return bft_str.replace("Bft", "Бф").strip()


def build_mingaweda_message(d: MingaWedaData) -> str:
    """Строит HTML-сообщение для Telegram из объекта MingaWedaData (на русском)."""

    lines = []
    lines.append("🌤 <b>Погода в Мюнхене (MingaWeda)</b>")

    # Время: вырезаем из немецкого timestamp только время и дату
    if d.timestamp:
        # «Wetter-Überblick von heute, Montag, dem 25.5.2026, um 15:41 Uhr»
        m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4}).*?(\d{2}:\d{2})\s*Uhr", d.timestamp)
        if m:
            lines.append(f"🕐 {m.group(1)}, {m.group(2)} (местн.)")
        else:
            lines.append(f"🕐 {d.timestamp}")

    lines.append("")

    # Температура
    if d.temp:
        temp_line = f"🌡 <b>Температура:</b> {d.temp}"
        if d.temp_trend:
            temp_line += f"  ({_trend(d.temp_trend)})"
        if d.temp_feels:
            temp_line += f"\n      ощущается: {d.temp_feels}"
        lines.append(temp_line)

    # Давление
    if d.pressure:
        pres_line = f"🔵 <b>Давление:</b> {d.pressure}"
        if d.pressure_trend:
            pres_line += f"  ({_trend(d.pressure_trend)})"
        lines.append(pres_line)

    # Ветер
    if d.wind_speed:
        wind_line = f"💨 <b>Ветер:</b> {d.wind_speed}"
        if d.wind_bft:
            wind_line += f" ({_bft_ru(d.wind_bft)})"
        if d.wind_dir:
            wind_line += f", {_dir_ru(d.wind_dir)}"
        lines.append(wind_line)

    # Порывы
    if d.gust_speed:
        gust_line = f"   порывы до: {d.gust_speed}"
        if d.gust_bft:
            gust_line += f" ({_bft_ru(d.gust_bft)})"
        lines.append(gust_line)

    # Осадки
    if d.rain:
        lines.append(f"🌧 <b>Осадки:</b> {_rain_ru(d.rain)}")

    # Влажность
    if d.humidity_rel:
        hum_line = f"💦 <b>Влажность:</b> {d.humidity_rel}"
        if d.humidity_abs:
            hum_line += f" / {d.humidity_abs}"
        if d.humidity_label:
            hum_line += f"  — {_HUMIDITY_RU.get(d.humidity_label, d.humidity_label)}"
        lines.append(hum_line)

    # Облачность
    if d.clouds:
        lines.append(f"☁️ <b>Облачность:</b> {_clouds_ru(d.clouds)}")

    lines.append("")
    lines.append('<a href="https://www.mingaweda.de/">mingaweda.de</a>')

    return "\n".join(lines)
