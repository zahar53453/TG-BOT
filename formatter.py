"""Telegram message formatters."""

import re
from typing import Optional

from decoder import decode_noaa_metar, decode_taf_raw, decode_weather


def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(icao: str, raw_data: dict) -> Optional[str]:
    """Legacy AirportWeather formatter kept for auxiliary scripts."""
    d = decode_weather(icao, raw_data)
    if d is None:
        return None

    sep = "—" * 30
    lines = [
        f"{d['flight_rules_emoji']} <b>{esc(d['airport_name'])}</b>",
        f"<code>{sep}</code>",
        f"🕐 <b>Время:</b>        <code>{esc(d['publish_time'])}</code>",
        f"🌡 <b>Температура:</b>  <code>{esc(d['temperature'])}</code>  <i>(точка росы: {esc(d['dew_point'])})</i>",
        f"☁️ <b>Облачность:</b>   <code>{esc(d['cloud_cover'])}</code>",
        f"📏 <b>Потолок:</b>      <code>{esc(d['ceiling'])}</code>",
        f"💨 <b>Ветер:</b>        <code>{esc(d['wind'])}</code>",
        f"👁 <b>Видимость:</b>    <code>{esc(d['visibility'])}</code>",
        f"🔵 <b>QNH:</b>          <code>{esc(d['qnh'])}</code>",
        f"✈️ <b>Категория:</b>    <code>{esc(d['flight_rules'])}</code>",
    ]

    if d["aw_metar"]:
        lines += [
            f"<code>{sep}</code>",
            "📡 <b>AW-METAR:</b>",
            f"<code>{esc(d['aw_metar'])}</code>",
        ]

    if d["aw_taf"]:
        lines += [f"<code>{sep}</code>", "📋 <b>AW-TAF:</b>"]
        lines.extend(f"<code>{esc(line)}</code>" for line in _format_taf(d["aw_taf"]))

    if d["original_metar"]:
        lines += [
            f"<code>{sep}</code>",
            "📻 <b>METAR (официальный):</b>",
            f"<code>{esc(d['original_metar'])}</code>",
        ]

    return "\n".join(lines)


def _format_taf(taf_str: str) -> list[str]:
    parts = re.split(r"(?=\b(?:FM|BECMG|TEMPO|PROB\d{2})\b)", taf_str.strip())
    result: list[str] = []
    for index, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        result.append(part if index == 0 else "  " + part)
    return result if result else [taf_str]


def build_metar_message(icao: str, metar: dict) -> Optional[str]:
    d = decode_noaa_metar(icao, metar)
    if d is None:
        return None

    sep = "—" * 30
    mtype = d.get("metar_type", "METAR")
    lines = [
        f"📻 {d['flight_rules_emoji']} <b>{esc(d['airport_name'])} — {esc(mtype)}</b>",
        f"<code>{sep}</code>",
        f"🕐 <b>Время наблюдения:</b>  <code>{esc(d['report_time'])}</code>",
        f"🌡 <b>Температура:</b>       <code>{esc(d['temperature'])}</code>  <i>(точка росы: {esc(d['dew_point'])})</i>",
        f"☁️ <b>Облачность:</b>        <code>{esc(d['cloud_cover'])}</code>",
        f"💨 <b>Ветер:</b>             <code>{esc(d['wind'])}</code>",
        f"👁 <b>Видимость:</b>         <code>{esc(d['visibility'])}</code>",
        f"🔵 <b>QNH:</b>               <code>{esc(d['qnh'])}</code>",
        f"✈️ <b>Категория:</b>         <code>{esc(d['flight_rules'])}</code>",
    ]

    if d["raw_ob"]:
        lines += [f"<code>{sep}</code>", f"<code>{esc(d['raw_ob'])}</code>"]

    return "\n".join(lines)


def build_taf_message(icao: str, taf_raw: str) -> Optional[str]:
    d = decode_taf_raw(icao, taf_raw)
    if d is None:
        return None

    sep = "—" * 30
    lines = [
        f"📝 <b>{esc(d['airport_name'])} — {esc(d['taf_type'])}</b>",
        f"<code>{sep}</code>",
        f"🕒 <b>Выпуск:</b>      <code>{esc(d['issue_time'])}</code>",
        f"📅 <b>Валидность:</b>  <code>{esc(d['validity'])}</code>",
        f"<code>{sep}</code>",
        "📌 <b>Основной прогноз:</b>",
    ]

    lines.extend(_render_taf_section(d["base"]))

    if d["sections"]:
        lines += [f"<code>{sep}</code>", "🔄 <b>Изменения по прогнозу:</b>"]
        for section in d["sections"]:
            lines.extend(_render_taf_section(section))

    lines += [f"<code>{sep}</code>", "📋 <b>Raw TAF:</b>"]
    lines.extend(f"<code>{esc(line)}</code>" for line in _format_taf(d["raw_taf"]))
    return "\n".join(lines)


def _render_taf_section(section: dict) -> list[str]:
    lines: list[str] = []
    label = section.get("label", "")
    if label == "BASE":
        title = "Основные условия"
    elif label == "FM":
        title = "Начиная с"
    elif label == "BECMG":
        title = "Постепенно"
    elif label == "TEMPO":
        title = "Временно"
    elif label == "INTER":
        title = "Периодически"
    elif label.startswith("PROB"):
        title = f"Вероятность {label[4:]}%"
    else:
        title = label

    period_text = section.get("period_decoded", "")
    heading = f"• <b>{esc(title)}:</b>"
    if period_text:
        heading += f" <code>{esc(period_text)}</code>"
    lines.append(heading)

    if section.get("wind"):
        lines.append(f"Ветер: <code>{esc(section['wind'])}</code>")
    if section.get("visibility"):
        lines.append(f"Видимость: <code>{esc(section['visibility'])}</code>")
    if section.get("weather"):
        lines.append(f"Погода: <code>{esc('; '.join(section['weather']))}</code>")
    if section.get("clouds"):
        lines.append(f"Облачность: <code>{esc('; '.join(section['clouds']))}</code>")
    if section.get("extras"):
        lines.append(f"Дополнительно: <code>{esc(' '.join(section['extras']))}</code>")

    return lines
