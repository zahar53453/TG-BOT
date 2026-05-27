"""
blick_formatter.py — Форматирование DWD-данных blick-aufs-wetter.com для Telegram.
Все подписи на русском языке.
"""

import re
from blick_fetcher import BlickData


# ── Направления ветра ────────────────────────────────────────────────────────
def _dir_to_name(deg_str: str) -> str:
    """«320» → «СЗ»"""
    try:
        d = int(deg_str)
    except (ValueError, TypeError):
        return deg_str or "—"
    dirs = [
        (11,  "С"),  (34,  "ССВ"), (56,  "СВ"), (79,  "ВСВ"),
        (101, "В"),  (124, "ВЮВ"), (146, "ЮВ"), (169, "ЮЮВ"),
        (191, "Ю"),  (214, "ЮЮЗ"), (236, "ЮЗ"), (259, "ЗЮЗ"),
        (281, "З"),  (304, "ЗСЗ"), (326, "СЗ"), (349, "ССЗ"),
        (360, "С"),
    ]
    for threshold, name in dirs:
        if d <= threshold:
            return name
    return "С"


def _fmt_time(raw: str) -> str:
    """«25.05 - 21:20 Uhr» → «25.05, 21:20 (местн.)»"""
    # Формат: «25.05 - 21:20 Uhr»
    m = re.search(r"(\d{1,2}\.\d{1,2})\s*-\s*(\d{2}:\d{2})", raw)
    if m:
        return f"{m.group(1)}, {m.group(2)} (местн.)"
    return raw


def build_blick_message(d: BlickData) -> str:
    """Строит HTML-сообщение для Telegram из объекта BlickData."""

    lines = ["🌤 <b>Погода EDDM — DWD Мюнхен Аэропорт</b>"]

    if d.datetime_str:
        lines.append(f"🕐 {_fmt_time(d.datetime_str)}")

    lines.append("")

    # Температура
    if d.temp:
        lines.append(f"🌡 <b>Температура:</b> {d.temp} °C")

    # Точка росы + влажность
    if d.dewpoint or d.humidity:
        parts = []
        if d.dewpoint:
            parts.append(f"точка росы: {d.dewpoint} °C")
        if d.humidity:
            parts.append(f"влажность: {d.humidity} %")
        lines.append(f"💦 {' / '.join(parts)}")

    # Ветер
    if d.gust or d.wind_dir:
        dir_deg = d.wind_dir or "—"
        dir_name = _dir_to_name(d.wind_dir) if d.wind_dir else "—"
        gust_str = f"{d.gust} км/ч" if d.gust else "—"
        lines.append(f"💨 <b>Порывы ветра:</b> {gust_str}, {dir_name} ({dir_deg}°)")

    # Давление
    if d.pressure:
        lines.append(f"🔵 <b>Давление:</b> {d.pressure} hPa")

    # Осадки
    if d.precip:
        precip_val = d.precip.replace(",", ".")
        try:
            pf = float(precip_val)
            if pf > 0:
                lines.append(f"🌧 <b>Осадки:</b> {precip_val} мм (за 10 мин)")
            else:
                lines.append(f"🌧 <b>Осадки:</b> нет")
        except ValueError:
            lines.append(f"🌧 <b>Осадки:</b> {d.precip}")

    lines.append("")
    lines.append(
        '<a href="https://www.blick-aufs-wetter.com/messwerte/ort/'
        'M%C3%BCnchen-Flughafen/01262">blick-aufs-wetter.com · DWD</a>'
    )

    return "\n".join(lines)
