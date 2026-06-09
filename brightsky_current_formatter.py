"""Telegram formatter for Bright Sky current SYNOP observations."""

from datetime import datetime

from brightsky_current_fetcher import BrightSkyCurrentObservation


_CONDITION_RU = {
    "dry": "сухо",
    "fog": "туман",
    "rain": "дождь",
    "snow": "снег",
    "sleet": "мокрый снег",
    "hail": "град",
    "thunderstorm": "гроза",
}


def _fmt_utc(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except Exception:
        return iso_str or "нет данных"


def _wind_dir_ru(deg) -> str:
    if deg is None:
        return ""
    dirs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
            "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return dirs[int((float(deg) + 11.25) / 22.5) % 16]


def _fmt_temp(value: float | None) -> str:
    return f"{value:+.1f}°C" if value is not None else "нет данных"


def _kmh_to_ms(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 3.6


def _fmt_speed_kmh(value: float | None) -> str:
    if value is None:
        return "нет данных"
    ms = _kmh_to_ms(value)
    return f"{ms:.1f} м/с ({value:.1f} км/ч)"


def _fmt_visibility(value: int | None) -> str:
    if value is None:
        return "нет данных"
    if value >= 1000:
        return f"{value / 1000:.1f} км"
    return f"{value} м"


def _fmt_wind(direction: int | None, speed_kmh: float | None, gust_kmh: float | None = None) -> str:
    if speed_kmh is None:
        return "нет данных"
    parts = []
    if direction is not None:
        parts.append(f"{direction:03d}° ({_wind_dir_ru(direction)})")
    parts.append(_fmt_speed_kmh(speed_kmh))
    if gust_kmh is not None:
        parts.append(f"порывы до {_fmt_speed_kmh(gust_kmh)}")
    return ", ".join(parts)


def _fmt_precip(obs: BrightSkyCurrentObservation) -> str:
    items = []
    if obs.precipitation_10_mm is not None:
        items.append(f"10 мин: {obs.precipitation_10_mm:.1f} мм")
    if obs.precipitation_30_mm is not None:
        items.append(f"30 мин: {obs.precipitation_30_mm:.1f} мм")
    if obs.precipitation_60_mm is not None:
        items.append(f"60 мин: {obs.precipitation_60_mm:.1f} мм")
    return ", ".join(items) if items else "нет данных"


def build_brightsky_current_message(obs: BrightSkyCurrentObservation) -> str:
    sep = "-" * 30
    condition = _CONDITION_RU.get(obs.condition, obs.condition or "нет данных")
    source_bits = [f"WMO {obs.wmo_station_id}"]
    if obs.dwd_station_id:
        source_bits.append(f"DWD {obs.dwd_station_id}")

    lines = [
        f"🌤 <b>Bright Sky SYNOP — {obs.station_name}</b>",
        f"<code>{sep}</code>",
        f"🕒 <b>Время наблюдения:</b> <code>{_fmt_utc(obs.observed_at)}</code>",
        f"🌡 <b>Температура:</b>      <code>{_fmt_temp(obs.temperature_c)}</code>  <i>(точка росы: {_fmt_temp(obs.dewpoint_c)})</i>",
        f"💧 <b>Влажность:</b>       <code>{int(obs.humidity_pct)}%</code>" if obs.humidity_pct is not None else "💧 <b>Влажность:</b>       <code>нет данных</code>",
        f"💨 <b>Ветер 10 мин:</b>    <code>{_fmt_wind(obs.wind_direction_10_deg, obs.wind_speed_10_kmh, obs.wind_gust_speed_10_kmh)}</code>",
        f"💨 <b>Ветер 30 мин:</b>    <code>{_fmt_wind(obs.wind_direction_30_deg, obs.wind_speed_30_kmh)}</code>",
        f"💨 <b>Ветер 60 мин:</b>    <code>{_fmt_wind(obs.wind_direction_60_deg, obs.wind_speed_60_kmh)}</code>",
        f"🔵 <b>Давление MSL:</b>    <code>{obs.pressure_msl_hpa:.1f} гПа</code>" if obs.pressure_msl_hpa is not None else "🔵 <b>Давление MSL:</b>    <code>нет данных</code>",
        f"👁 <b>Видимость:</b>       <code>{_fmt_visibility(obs.visibility_m)}</code>",
        f"☁️ <b>Облачность:</b>      <code>{obs.cloud_cover_pct}%</code>" if obs.cloud_cover_pct is not None else "☁️ <b>Облачность:</b>      <code>нет данных</code>",
        f"🌦 <b>Осадки:</b>          <code>{_fmt_precip(obs)}</code>",
        f"📝 <b>Состояние:</b>       <code>{condition}</code>",
        f"<code>{sep}</code>",
        f"<i>Источник: Bright Sky / DWD SYNOP ({', '.join(source_bits)})</i>",
    ]
    return "\n".join(lines)
