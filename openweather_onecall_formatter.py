"""Formatter for OpenWeather One Call current observations."""

from datetime import datetime

from openweather_onecall_fetcher import OpenWeatherCurrentObservation


def _fmt_utc(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m, %H:%M UTC")
    except Exception:
        return iso_str


def _wind_dir_ru(deg) -> str:
    if deg is None:
        return ""
    dirs = [
        "С",
        "ССВ",
        "СВ",
        "ВСВ",
        "В",
        "ВЮВ",
        "ЮВ",
        "ЮЮВ",
        "Ю",
        "ЮЮЗ",
        "ЮЗ",
        "ЗЮЗ",
        "З",
        "ЗСЗ",
        "СЗ",
        "ССЗ",
    ]
    return dirs[int((float(deg) + 11.25) / 22.5) % 16]


def _fmt_temp(value: float | None) -> str:
    if value is None:
        return "нет данных"
    return f"{value:+.1f}°C"


def _fmt_visibility(value: int | None) -> str:
    if value is None:
        return "нет данных"
    if value >= 1000:
        return f"{value / 1000:.1f} км"
    return f"{value} м"


def _fmt_wind(obs: OpenWeatherCurrentObservation) -> str:
    if obs.windspeed_ms is None:
        return "нет данных"
    parts = []
    if obs.winddir_deg is not None:
        parts.append(f"{obs.winddir_deg:03d}° ({_wind_dir_ru(obs.winddir_deg)})")
    parts.append(f"{obs.windspeed_ms:.1f} м/с")
    if obs.windgust_ms is not None:
        parts.append(f"порывы до {obs.windgust_ms:.1f} м/с")
    return ", ".join(parts)


def _fmt_precip(obs: OpenWeatherCurrentObservation) -> str:
    items = []
    if obs.rain_1h_mm is not None:
        items.append(f"дождь {obs.rain_1h_mm:.1f} мм/ч")
    if obs.snow_1h_mm is not None:
        items.append(f"снег {obs.snow_1h_mm:.1f} мм/ч")
    return ", ".join(items) if items else "нет данных"


def build_openweather_current_message(obs: OpenWeatherCurrentObservation) -> str:
    sep = "-" * 30
    weather_label = obs.weather_description or obs.weather_main or "нет данных"

    lines = [
        f"🌤 <b>OpenWeather Nowcast — {obs.airport_name}</b>",
        f"<code>{sep}</code>",
        f"🕒 <b>Обновлено:</b>    <code>{_fmt_utc(obs.observed_at_utc)}</code>",
        f"📥 <b>Получено API:</b> <code>{_fmt_utc(obs.fetched_at_utc)}</code>",
        f"🌡 <b>Температура:</b>  <code>{_fmt_temp(obs.temperature_c)}</code>  <i>(ощущается как {_fmt_temp(obs.feels_like_c)}, точка росы: {_fmt_temp(obs.dewpoint_c)})</i>",
        f"💧 <b>Влажность:</b>    <code>{obs.humidity_pct}%</code>" if obs.humidity_pct is not None else "💧 <b>Влажность:</b>    <code>нет данных</code>",
        f"💨 <b>Ветер:</b>        <code>{_fmt_wind(obs)}</code>",
        f"👁 <b>Видимость:</b>    <code>{_fmt_visibility(obs.visibility_m)}</code>",
        f"🔵 <b>Давление:</b>     <code>{obs.pressure_hpa} гПа</code>" if obs.pressure_hpa is not None else "🔵 <b>Давление:</b>     <code>нет данных</code>",
        f"☁️ <b>Облачность:</b>   <code>{obs.cloudiness_pct}%</code>" if obs.cloudiness_pct is not None else "☁️ <b>Облачность:</b>   <code>нет данных</code>",
        f"🌦 <b>Осадки:</b>       <code>{_fmt_precip(obs)}</code>",
        f"📝 <b>Погода:</b>       <code>{weather_label}</code>",
    ]

    lines += [
        f"<code>{sep}</code>",
        "<i>Source: OpenWeather One Call 3.0</i>",
    ]
    return "\n".join(lines)
