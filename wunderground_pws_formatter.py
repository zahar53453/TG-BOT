"""Formatter for Weather Underground PWS observations near Munich Airport."""

from datetime import datetime

from wunderground_pws_fetcher import WundergroundPwsObservation


def _fmt_local_time(obs: WundergroundPwsObservation) -> str:
    raw = obs.observed_at_local
    if not raw:
        return obs.observed_at_utc
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m, %H:%M")
    except Exception:
        return raw


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


def _fmt_wind(obs: WundergroundPwsObservation) -> str:
    if obs.windspeed_ms is None:
        return "нет данных"
    parts = []
    if obs.winddir_deg is not None:
        parts.append(f"{int(obs.winddir_deg):03d}° ({_wind_dir_ru(obs.winddir_deg)})")
    parts.append(f"{obs.windspeed_ms:.1f} м/с")
    if obs.windgust_ms is not None:
        parts.append(f"порывы до {obs.windgust_ms:.1f} м/с")
    return ", ".join(parts)


def _fmt_precip(obs: WundergroundPwsObservation) -> str:
    if obs.precip_rate_mm_h is None and obs.precip_total_mm is None:
        return "нет данных"
    rate = f"{obs.precip_rate_mm_h:.2f} мм/ч" if obs.precip_rate_mm_h is not None else "н/д"
    total = f"{obs.precip_total_mm:.2f} мм" if obs.precip_total_mm is not None else "н/д"
    return f"rate {rate}, total {total}"


def build_wunderground_pws_message(obs: WundergroundPwsObservation) -> str:
    sep = "-" * 30
    lines = [
        f"🌤 <b>Weather Underground PWS — {obs.station_name}</b>",
        f"<code>{sep}</code>",
        f"🕒 <b>Время:</b>        <code>{_fmt_local_time(obs)} (местн.)</code>",
        f"🌡 <b>Температура:</b>  <code>{_fmt_temp(obs.temperature_c)}</code>  <i>(точка росы: {_fmt_temp(obs.dewpoint_c)})</i>",
        f"💧 <b>Влажность:</b>    <code>{int(obs.humidity_pct)}%</code>" if obs.humidity_pct is not None else "💧 <b>Влажность:</b>    <code>нет данных</code>",
        f"💨 <b>Ветер:</b>        <code>{_fmt_wind(obs)}</code>",
        f"🔵 <b>Давление:</b>     <code>{obs.pressure_hpa:.2f} гПа</code>" if obs.pressure_hpa is not None else "🔵 <b>Давление:</b>     <code>нет данных</code>",
        f"🌧 <b>Осадки:</b>       <code>{_fmt_precip(obs)}</code>",
    ]

    if obs.uv_index is not None:
        lines.append(f"☀️ <b>UV:</b>           <code>{obs.uv_index:.1f}</code>")
    if obs.solar_radiation_wm2 is not None:
        lines.append(f"🔆 <b>Радиация:</b>     <code>{obs.solar_radiation_wm2:.1f} W/m²</code>")
    if obs.pressure_trend_hpa is not None:
        lines.append(f"📈 <b>Тренд давл.:</b>  <code>{obs.pressure_trend_hpa:+.2f} гПа</code>")

    lines += [
        f"<code>{sep}</code>",
        f'<a href="{obs.dashboard_url}">{obs.station_id} on Weather Underground</a>',
    ]
    return "\n".join(lines)
