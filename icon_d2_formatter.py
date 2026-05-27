"""Telegram formatter for ICON forecasts."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from icon_d2_fetcher import IconD2Forecast


def _weather_icon(code) -> str:
    if code is None:
        return "🌡"
    if code == 0:
        return "☀️"
    if code == 1:
        return "🌤"
    if code == 2:
        return "⛅"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫"
    if code in (51, 53, 55):
        return "🌦"
    if code in (61, 63, 65, 80, 81, 82):
        return "🌧"
    if code in (71, 73, 75, 77, 85, 86):
        return "🌨"
    if code in (95, 96, 99):
        return "⛈"
    return "🌡"


def _dir_ru(deg) -> str:
    if deg is None:
        return ""
    dirs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
            "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return dirs[int((deg + 11.25) / 22.5) % 16]


def _fmt_run_time(utc_str: str) -> str:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", utc_str)
    if not match:
        return utc_str
    _, month, day, hour, minute = match.groups()
    return f"{day}.{month}, {hour}:{minute} UTC"


def _fmt_local(iso: str) -> str:
    match = re.search(r"T(\d{2}:\d{2})", iso)
    return match.group(1) if match else iso


def _fmt_date(iso: str) -> str:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", iso)
    if not match:
        return iso
    year, month, day = (int(item) for item in match.groups())
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    weekday = datetime(year, month, day).weekday()
    return f"{day:02d}.{month:02d} ({days_ru[weekday]})"


def build_icon_d2_message(fc: IconD2Forecast) -> str:
    tz = ZoneInfo(fc.timezone_name)
    now_local = datetime.now(tz).replace(minute=0, second=0, microsecond=0, tzinfo=None)

    lines = [
        f"📊 <b>{fc.model.upper()} — Прогноз {fc.icao}</b>",
        f"📍 <b>{fc.airport_name}</b>",
        f"🔄 Запуск модели: <b>{_fmt_run_time(fc.model_run_utc)}</b>",
    ]

    current_idx = 0
    for i, forecast_time in enumerate(fc.times):
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", forecast_time)
        if not match:
            continue
        year, month, day, hour, minute = (int(item) for item in match.groups())
        forecast_local = datetime(year, month, day, hour, minute)
        if forecast_local >= now_local:
            current_idx = i
            break

    hours_to_show = min(25, len(fc.times) - current_idx)

    def pick(items, idx):
        return items[idx] if items and idx < len(items) else None

    current_date = None
    for i in range(hours_to_show):
        idx = current_idx + i
        forecast_time = fc.times[idx]
        temp = pick(fc.temps, idx)
        wind = pick(fc.winds, idx)
        wind_dir = pick(fc.wind_dirs, idx)
        precip = pick(fc.precips, idx)
        weather_code = pick(fc.weather_codes, idx)
        cloud = pick(fc.clouds, idx)

        date_str = _fmt_date(forecast_time)
        hour_str = _fmt_local(forecast_time)
        icon = _weather_icon(weather_code)
        temp_str = f"{temp:+.1f}°C" if temp is not None else "?"

        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n📅 <b>{date_str}</b>")

        prefix = "▶️" if i == 0 else "   "
        cloud_str = f" ☁️{cloud:.0f}%" if cloud is not None else ""
        wind_str = f" 💨{_dir_ru(wind_dir)} {wind:.0f}" if wind is not None and wind_dir is not None else ""
        precip_str = f" 🌧{precip:.1f}мм" if precip is not None and precip > 0.0 else ""
        lines.append(f"{prefix} {icon} {hour_str}  <b>{temp_str}</b>{cloud_str}{wind_str}{precip_str}")

    lines.append("")
    lines.append(
        f'<a href="https://open-meteo.com">Open-Meteo</a> · '
        f'{fc.model.upper()}'
    )
    return "\n".join(lines)
