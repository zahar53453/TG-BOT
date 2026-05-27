"""Formatter for Météo-France 6-minute observations."""

from datetime import datetime

from meteofrance_obs_fetcher import MeteoFranceObservation


def _fmt_utc(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y  %H:%M UTC")
    except Exception:
        return iso_str


def _wind_dir_ru(deg) -> str:
    if deg is None:
        return ""
    dirs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
            "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return dirs[int((float(deg) + 11.25) / 22.5) % 16]


def _fmt_wind(obs: MeteoFranceObservation) -> str:
    if obs.wind_speed_ms is None:
        return "нет данных"
    if obs.wind_dir_deg is None:
        base = f"{obs.wind_speed_ms:.1f} м/с"
    else:
        base = f"{int(obs.wind_dir_deg):03d}° ({_wind_dir_ru(obs.wind_dir_deg)}), {obs.wind_speed_ms:.1f} м/с"
    if obs.gust_speed_ms is not None:
        base += f", порывы до {obs.gust_speed_ms:.1f} м/с"
    return base


def build_meteofrance_obs_message(obs: MeteoFranceObservation) -> str:
    sep = "—" * 30
    lines = [
        f"🇫🇷 <b>Météo-France 6 минут — {obs.station_name}</b>",
        f"<code>{sep}</code>",
        f"🕐 <b>Валидность:</b>   <code>{_fmt_utc(obs.validity_time)}</code>",
        f"📥 <b>Получено API:</b> <code>{_fmt_utc(obs.insert_time)}</code>",
    ]

    if obs.temp_c is not None:
        dew = f"{obs.dewpoint_c:+.1f}°C" if obs.dewpoint_c is not None else "нет данных"
        lines.append(f"🌡 <b>Температура:</b>  <code>{obs.temp_c:+.1f}°C</code>  <i>(точка росы: {dew})</i>")
    if obs.humidity_pct is not None:
        lines.append(f"💧 <b>Влажность:</b>    <code>{int(obs.humidity_pct)}%</code>")

    lines.append(f"💨 <b>Ветер:</b>        <code>{_fmt_wind(obs)}</code>")

    if obs.precipitation_mm is not None:
        lines.append(f"🌧 <b>Осадки 6 мин:</b> <code>{float(obs.precipitation_mm):.1f} мм</code>")
    if obs.pressure_hpa is not None:
        lines.append(f"🔵 <b>Давление:</b>     <code>{obs.pressure_hpa:.1f} гПа</code>")
    if obs.sea_level_pressure_hpa is not None:
        lines.append(f"🌍 <b>QNH/SLP:</b>      <code>{obs.sea_level_pressure_hpa:.1f} гПа</code>")

    lines += [
        f"<code>{sep}</code>",
        "<i>Source: Météo-France DPObs 6m</i>",
    ]
    return "\n".join(lines)
