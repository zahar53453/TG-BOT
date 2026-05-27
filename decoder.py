"""
decoder.py — Расшифровка данных погоды из JSON в понятный текст.

Парсит поля из weather.nowcast (AW-METAR/AW-TAF данные Meandair)
и из weather.metar (оригинальный METAR при наличии).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import math
import re


# ── Словари для расшифровки ──────────────────────────────────────────────────

FLIGHT_RULES = {
    "VFR":  ("🟢", "VFR — визуальные правила"),
    "MVFR": ("🔵", "MVFR — граничные визуальные"),
    "IFR":  ("🔴", "IFR — приборные правила"),
    "LIFR": ("🟣", "LIFR — низкий IFR"),
}

CLOUD_COVER = {
    "SKC":  "ясно (0 окт)",
    "CLR":  "ясно (0 окт)",
    "FEW":  "мало (1–2 окт)",
    "SCT":  "рассеяно (3–4 окт)",
    "BKN":  "значительная (5–7 окт)",
    "OVC":  "сплошная (8 окт)",
    "NSC":  "без значимой облачности",
    "NCD":  "без облаков",
    "VV":   "вертикальная видимость",
}

# Стороны света для ветра
WIND_DIRS = [
    "С", "ССВ", "СВ", "ВСВ",
    "В", "ВЮВ", "ЮВ", "ЮЮВ",
    "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ",
    "З", "ЗСЗ", "СЗ", "ССЗ",
]

# Названия аэропортов
AIRPORT_NAMES = {
    "EGLC": "Лондон Сити (EGLC)",
    "EGLL": "Лондон Хитроу (EGLL)",
    "EGKK": "Лондон Гатвик (EGKK)",
    "UUEE": "Москва Шереметьево (UUEE)",
    "UUDD": "Москва Домодедово (UUDD)",
    "UUWW": "Москва Внуково (UUWW)",
    "UKBB": "Киев Борисполь (UKBB)",
    "LEMD": "Мадрид Барахас (LEMD)",
    "LFPB": "Париж Ле-Бурже (LFPB)",
    "LFPG": "Париж Шарль-де-Голль (LFPG)",
    "EDDF": "Франкфурт (EDDF)",
    "EDDM": "Мюнхен (EDDM)",
}


# ── Вспомогательные функции ──────────────────────────────────────────────────

def ms_to_kt(ms: float) -> int:
    """Метры/с → узлы."""
    return round(ms * 1.94384)


def m_to_ft(m: float) -> int:
    """Метры → футы."""
    return round(m * 3.28084)


def direction_to_compass(deg: float) -> str:
    """Градусы → буквенное направление."""
    idx = round(deg / 22.5) % 16
    return WIND_DIRS[idx]


def format_visibility(m: float) -> str:
    """Форматирует видимость."""
    if m >= 9999:
        return "10+ км"
    elif m >= 1000:
        return f"{m / 1000:.1f} км".rstrip("0").rstrip(".")
    else:
        return f"{round(m)} м"


def format_publish_time(iso_str: str) -> str:
    """Форматирует publish_time в читаемый вид (UTC)."""
    # Пример: "2026-05-22T14:30:30+01:00[Europe/London]"
    # Обрезаем часть с [] (нестандартный формат)
    clean = iso_str.split("[")[0]  # -> "2026-05-22T14:30:30+01:00"
    try:
        dt = datetime.fromisoformat(clean)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.strftime("%d %b %Y  %H:%M UTC")
    except Exception:
        return iso_str[:16].replace("T", " ")


def parse_cloud_cover_fraction(fraction: float) -> str:
    """Доля облачности (0–1) → текст."""
    oktas = round(fraction * 8)
    if oktas == 0:
        return "ясно (SKC)"
    elif oktas <= 2:
        return f"мало, {oktas} окт (FEW)"
    elif oktas <= 4:
        return f"рассеяно, {oktas} окт (SCT)"
    elif oktas <= 7:
        return f"значительная, {oktas} окт (BKN)"
    else:
        return "сплошная, 8 окт (OVC)"


def parse_ceiling(ceiling_steps: list) -> str:
    """Нижняя граница облаков из time_steps."""
    if not ceiling_steps:
        return "нет данных"
    step = ceiling_steps[0]
    qty = step.get("quantity", {})
    if isinstance(qty, dict):
        if qty.get("meaning") == "no ceiling":
            return "не ограничена"
        val = qty.get("value")
        if val is not None:
            return f"{m_to_ft(val):,} фут ({round(val)} м)".replace(",", " ")
    return "нет данных"


# ── Главная функция декодирования ────────────────────────────────────────────

def decode_weather(icao: str, raw_data: dict) -> Optional[dict]:
    """
    Извлекает и декодирует все поля из JSON-ответа API.
    Возвращает словарь с готовыми для отображения строками.
    """
    try:
        weather = raw_data["weather"]
        nowcast = weather["nowcast"]
    except (KeyError, TypeError):
        return None

    result = {}

    # ── Аэропорт ────────────────────────────────────────────────────────────
    result["airport_name"] = AIRPORT_NAMES.get(icao.upper(), f"{icao.upper()}")
    result["icao"] = icao.upper()

    # ── Время публикации ─────────────────────────────────────────────────────
    publish_time = nowcast.get("publish_time", "")
    result["publish_time_raw"] = publish_time
    result["publish_time"] = format_publish_time(publish_time)

    # ── Категория полётов ────────────────────────────────────────────────────
    try:
        fr_code = nowcast["flight_rules"]["time_steps"][0]["quantity"]["meaning"]
        emoji, fr_text = FLIGHT_RULES.get(fr_code, ("⚪", fr_code))
    except (KeyError, IndexError, TypeError):
        emoji, fr_text = "⚪", "нет данных"
    result["flight_rules_emoji"] = emoji
    result["flight_rules"] = fr_text

    # ── Ветер ────────────────────────────────────────────────────────────────
    try:
        wind_step = nowcast["wind_10m_agl"]["time_steps"][0]
        spd_ms = wind_step["speed"]["value"]
        dir_deg = wind_step["from_direction"]["value"]
        gust_ms = wind_step.get("gust_speed", {})
        gust_ms = gust_ms.get("value") if isinstance(gust_ms, dict) else None

        spd_kt = ms_to_kt(spd_ms)
        dir_deg_int = round(dir_deg)
        compass = direction_to_compass(dir_deg)

        wind_str = f"{dir_deg_int:03d}° ({compass}) / {spd_kt} кт ({round(spd_ms)} м/с)"
        if gust_ms and gust_ms > spd_ms:
            wind_str += f", порывы {ms_to_kt(gust_ms)} кт ({round(gust_ms)} м/с)"
    except (KeyError, IndexError, TypeError):
        wind_str = "нет данных"
    result["wind"] = wind_str

    # ── Температура и точка росы ─────────────────────────────────────────────
    try:
        temp_c = nowcast["air_temperature_2m_agl"]["time_steps"][0]["quantity"]["value"]
        result["temperature"] = f"{temp_c:.1f}°C"
    except (KeyError, IndexError, TypeError):
        result["temperature"] = "нет данных"

    try:
        dew_c = nowcast["dew_point_temperature_2m_agl"]["time_steps"][0]["quantity"]["value"]
        result["dew_point"] = f"{dew_c:.1f}°C"
    except (KeyError, IndexError, TypeError):
        result["dew_point"] = "нет данных"

    # ── Видимость ────────────────────────────────────────────────────────────
    try:
        vis_m = nowcast["surface_visibility"]["time_steps"][0]["quantity"]["value"]
        result["visibility"] = format_visibility(vis_m)
    except (KeyError, IndexError, TypeError):
        result["visibility"] = "нет данных"

    # ── Облачность ───────────────────────────────────────────────────────────
    try:
        cover_fraction = nowcast["cloud_cover"]["time_steps"][0]["quantity"]["value"]
        result["cloud_cover"] = parse_cloud_cover_fraction(cover_fraction)
    except (KeyError, IndexError, TypeError):
        result["cloud_cover"] = "нет данных"

    # ── Нижняя граница облаков (потолок) ─────────────────────────────────────
    try:
        ceiling_steps = nowcast["ceiling_agl"]["time_steps"]
        result["ceiling"] = parse_ceiling(ceiling_steps)
    except (KeyError, TypeError):
        result["ceiling"] = "нет данных"

    # ── QNH ─────────────────────────────────────────────────────────────────
    try:
        qnh_raw = nowcast["air_pressure_qnh"]["time_steps"][0]["quantity"]["value"]
        unit = nowcast["air_pressure_qnh"]["time_steps"][0]["quantity"].get("unit", "")
        # API может вернуть Па (> 2000) или гПа напрямую
        if unit == "Pa" or qnh_raw > 2000:
            qnh_hpa = round(qnh_raw / 100)
        else:
            qnh_hpa = round(qnh_raw)
        qnh_inhg = round(qnh_hpa * 0.02953, 2)
        result["qnh"] = f"{qnh_hpa} гПа / {qnh_inhg:.2f} inHg"
    except (KeyError, IndexError, TypeError):
        result["qnh"] = "нет данных"

    # ── Сырые строки AW-METAR / AW-TAF ──────────────────────────────────────
    result["aw_metar"] = nowcast.get("synthetic_metar_report", "")
    result["aw_taf"] = nowcast.get("synthetic_taf_report", "")

    # ── Оригинальный METAR (если есть станция) ───────────────────────────────
    try:
        result["original_metar"] = weather["metar"].get("raw_report", "")
    except (KeyError, AttributeError, TypeError):
        result["original_metar"] = ""

    return result


# ── Декодирование официального METAR (NOAA) ─────────────────────────────────

def _fmt_noaa_report_time(iso_str: str) -> str:
    """Форматирует reportTime NOAA ('2026-05-22T13:20:00.000Z') в читаемый UTC."""
    try:
        # NOAA всегда даёт UTC (суффикс Z)
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d %b %Y  %H:%M UTC")
    except Exception:
        return iso_str[:16].replace("T", " ")


def _fmt_raw_metar_time(raw_ob: str, fallback_iso: str) -> str:
    """
    Предпочитает фактическое время из raw METAR (ddhhmmZ), а не reportTime AWC.
    Это важно для аэропортов, где raw-строка выходит в :20/:50 или :00/:30,
    а AWC reportTime может быть округлён до следующего часа.
    """
    if raw_ob:
        m = re.search(r"\b(\d{2})(\d{2})(\d{2})Z\b", raw_ob)
        if m:
            day, hour, minute = (int(x) for x in m.groups())
            try:
                base = datetime.fromisoformat(fallback_iso.replace("Z", "+00:00"))
                dt = base.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                return dt.strftime("%d %b %Y  %H:%M UTC")
            except Exception:
                return f"{day:02d} {hour:02d}:{minute:02d} UTC"
    return _fmt_noaa_report_time(fallback_iso)


def _fmt_noaa_wind(wdir, wspd, wgst) -> str:
    """Форматирует ветер из полей NOAA (направление в °T, скорость в узлах)."""
    if wdir is None or wspd is None:
        return "нет данных"
    try:
        compass = direction_to_compass(float(wdir))
        result = f"{int(wdir):03d}° ({compass}) / {int(wspd)} кт"
        if wgst:
            result += f", порывы {int(wgst)} кт"
        return result
    except Exception:
        return "нет данных"


def _fmt_noaa_visibility(visib) -> str:
    """Форматирует видимость NOAA (в статутных милях, может быть '6+' или число)."""
    if visib is None:
        return "нет данных"
    s = str(visib)
    if s == "6+" or s.startswith("6+"):
        return "10+ км (9999 м)"
    try:
        sm = float(s)
        km = sm * 1.852
        if km >= 10:
            return f"10+ км"
        return f"{km:.1f} км ({round(sm * 1852)} м)"
    except ValueError:
        return s


def _fmt_noaa_clouds(cover: str, clouds: list) -> str:
    """Расшифровывает облачность из полей cover и clouds NOAA."""
    # cover — общий покров: SKC, CLR, FEW, SCT, BKN, OVC
    cover_text = CLOUD_COVER.get(cover.upper(), cover) if cover else ""

    if not clouds:
        return cover_text or "нет данных"

    layers = []
    for layer in clouds:
        cov = layer.get("cover", "")
        base = layer.get("base")  # футы
        cov_text = CLOUD_COVER.get(cov.upper(), cov)
        if base is not None:
            layers.append(f"{cov_text} {int(base):,} фут".replace(",", " "))
        else:
            layers.append(cov_text)

    if layers:
        return "; ".join(layers)
    return cover_text or "нет данных"


def decode_noaa_metar(icao: str, metar: dict) -> Optional[dict]:
    """
    Декодирует поля официального METAR из NOAA JSON в читаемые строки.

    Входной dict — один элемент из ответа NOAA /api/data/metar.
    """
    if not metar:
        return None

    result: dict = {}

    result["airport_name"] = AIRPORT_NAMES.get(icao.upper(), icao.upper())
    result["icao"] = icao.upper()

    # Время наблюдения
    report_time = metar.get("reportTime", "")
    raw_ob = metar.get("rawOb", "")
    result["report_time_raw"] = report_time
    result["report_time"] = _fmt_raw_metar_time(raw_ob, report_time)

    # Тип METAR (METAR / SPECI)
    result["metar_type"] = metar.get("metarType", "METAR")

    # Категория полётов
    flt_cat = metar.get("fltCat", "")
    emoji, fr_text = FLIGHT_RULES.get(flt_cat.upper(), ("⚪", flt_cat or "нет данных"))
    result["flight_rules_emoji"] = emoji
    result["flight_rules"] = fr_text

    # Ветер
    result["wind"] = _fmt_noaa_wind(
        metar.get("wdir"), metar.get("wspd"), metar.get("wgst")
    )

    # Температура / точка росы
    temp = metar.get("temp")
    dewp = metar.get("dewp")
    result["temperature"] = f"{temp}°C" if temp is not None else "нет данных"
    result["dew_point"]   = f"{dewp}°C" if dewp is not None else "нет данных"

    # Видимость
    result["visibility"] = _fmt_noaa_visibility(metar.get("visib"))

    # Облачность
    result["cloud_cover"] = _fmt_noaa_clouds(
        metar.get("cover", ""), metar.get("clouds", [])
    )

    # QNH (NOAA: altim в гПа)
    altim = metar.get("altim")
    if altim:
        inhg = round(altim * 0.02953, 2)
        result["qnh"] = f"{int(altim)} гПа / {inhg:.2f} inHg"
    else:
        result["qnh"] = "нет данных"

    # Сырая строка
    result["raw_ob"] = raw_ob

    return result


TAF_CHANGE_MARKERS = {"FM", "BECMG", "TEMPO", "INTER"}
TAF_WEATHER_CODES = {
    "DZ": "морось",
    "RA": "дождь",
    "SN": "снег",
    "SG": "снежная крупа",
    "IC": "ледяные иглы",
    "PL": "ледяной дождь",
    "GR": "град",
    "GS": "мелкий град",
    "UP": "неопознанные осадки",
    "BR": "дымка",
    "FG": "туман",
    "FU": "дым",
    "VA": "вулканический пепел",
    "DU": "пыль",
    "SA": "песок",
    "HZ": "мгла",
    "PY": "поземок",
    "PO": "пылевые вихри",
    "SQ": "шквал",
    "FC": "воронка/торнадо",
    "SS": "песчаная буря",
    "DS": "пыльная буря",
    "SH": "ливневый характер",
    "TS": "гроза",
    "FZ": "переохлажденные",
    "MI": "поземный",
    "BC": "местами",
    "PR": "частичный",
    "DR": "низовая метель/перенос",
    "BL": "метель/поземок",
}


def _taf_reference_date() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_taf_day(day: int, reference: datetime) -> datetime:
    candidate = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        candidate = candidate.replace(day=day)
    except ValueError:
        candidate = (candidate + timedelta(days=32)).replace(day=day)

    if candidate - reference > timedelta(days=15):
        month = candidate.month - 1 or 12
        year = candidate.year - 1 if candidate.month == 1 else candidate.year
        candidate = candidate.replace(year=year, month=month, day=day)
    elif reference - candidate > timedelta(days=15):
        month = candidate.month + 1 if candidate.month < 12 else 1
        year = candidate.year + 1 if candidate.month == 12 else candidate.year
        candidate = candidate.replace(year=year, month=month, day=day)
    return candidate


def _format_dt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%d %b %Y %H:%M UTC")


def _parse_taf_issue_time(token: str, reference: datetime) -> Optional[datetime]:
    match = re.fullmatch(r"(\d{2})(\d{2})(\d{2})Z", token)
    if not match:
        return None
    day, hour, minute = map(int, match.groups())
    base = _resolve_taf_day(day, reference)
    return base.replace(hour=hour, minute=minute)


def _parse_taf_period(token: str, reference: datetime) -> Optional[tuple[datetime, datetime]]:
    match = re.fullmatch(r"(\d{2})(\d{2})/(\d{2})(\d{2})", token)
    if not match:
        return None
    start_day, start_hour, end_day, end_hour = map(int, match.groups())
    start = _resolve_taf_day(start_day, reference).replace(hour=start_hour, minute=0)
    end = _resolve_taf_day(end_day, reference).replace(hour=end_hour, minute=0)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _decode_taf_weather(token: str) -> str:
    intensity_prefix = ""
    rest = token
    if rest.startswith("+"):
        intensity_prefix = "сильный"
        rest = rest[1:]
    elif rest.startswith("-"):
        intensity_prefix = "слабый"
        rest = rest[1:]
    vicinity = False
    if rest.startswith("VC"):
        vicinity = True
        rest = rest[2:]

    parts = []
    while rest:
        code = rest[:2]
        rest = rest[2:]
        parts.append(TAF_WEATHER_CODES.get(code, code))

    text = " ".join(parts).strip()
    if text == "гроза дождь":
        text = "гроза с дождем"
    elif text == "гроза ливневый характер":
        text = "гроза с ливнями"
    elif text == "ливневый характер дождь":
        text = "ливневый дождь"
    elif text == "переохлажденные дождь":
        text = "переохлажденный дождь"
    elif text == "переохлажденные морось":
        text = "переохлажденная морось"

    if intensity_prefix:
        text = f"{intensity_prefix} {text}"
    if vicinity:
        text = f"в окрестности {text}"
    return text.strip()


def _decode_taf_visibility(token: str) -> str:
    if token == "9999":
        return "10+ км"
    if token == "P6SM":
        return "более 6 статутных миль (10+ км)"
    if token.endswith("SM"):
        return f"{token[:-2]} статутных миль"
    if token.isdigit():
        meters = int(token)
        return format_visibility(meters)
    return token


def _decode_taf_wind(token: str) -> str:
    match = re.fullmatch(r"(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?KT", token)
    if not match:
        return token
    direction, speed, _, gust = match.groups()
    speed_int = int(speed)
    if direction == "VRB":
        result = f"направление переменное, {speed_int} уз"
    else:
        compass = direction_to_compass(float(direction))
        result = f"{direction}° ({compass}), {speed_int} уз"
    if gust:
        result += f", порывы до {int(gust)} уз"
    return result


def _decode_taf_cloud(token: str) -> Optional[str]:
    if token == "NSW":
        return "значимых явлений погоды не ожидается"
    if token in {"CAVOK", "SKC", "NSC", "NCD"}:
        return CLOUD_COVER.get(token, token)
    match = re.fullmatch(r"(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?", token)
    if not match:
        return None
    cover, height, convective = match.groups()
    text = CLOUD_COVER.get(cover, cover)
    feet = int(height) * 100
    meters = round(feet * 0.3048)
    result = f"{text}, нижняя граница {feet:,} ft ({meters} м)".replace(",", " ")
    if convective == "CB":
        result += ", кучево-дождевые"
    elif convective == "TCU":
        result += ", мощные кучевые"
    return result


def _decode_taf_temperature_extreme(token: str, reference: datetime) -> Optional[str]:
    match = re.fullmatch(r"(TX|TN)(M?\d{2})/(\d{2})(\d{2})Z", token)
    if not match:
        return None
    kind, value_token, day_token, hour_token = match.groups()
    value = int(value_token.replace("M", ""))
    if value_token.startswith("M"):
        value = -value
    moment = _resolve_taf_day(int(day_token), reference).replace(hour=int(hour_token), minute=0)
    label = "максимальная температура" if kind == "TX" else "минимальная температура"
    return f"{label} {value}°C к {_format_dt_utc(moment)}"


def _decode_taf_wind_shear(token: str) -> Optional[str]:
    match = re.fullmatch(r"WS(\d{3})/(\d{3})(\d{2,3})KT", token)
    if not match:
        return None
    height_hundreds_ft, direction, speed = match.groups()
    height_ft = int(height_hundreds_ft) * 100
    compass = direction_to_compass(float(direction))
    return f"сдвиг ветра на {height_ft} ft: {direction}° ({compass}), {int(speed)} уз"


def _split_taf_sections(tokens: list[str]) -> list[dict]:
    sections: list[dict] = []
    current = {"label": "BASE", "period": "", "tokens": []}

    for token in tokens:
        if token.startswith("FM") and re.fullmatch(r"FM\d{6}", token):
            if current["tokens"]:
                sections.append(current)
            current = {"label": "FM", "period": token[2:], "tokens": []}
            continue
        if token in {"BECMG", "TEMPO", "INTER"} or re.fullmatch(r"PROB\d{2}", token):
            if current["tokens"]:
                sections.append(current)
            current = {"label": token, "period": "", "tokens": []}
            continue
        if current["label"] in {"BECMG", "TEMPO", "INTER"} or current["label"].startswith("PROB"):
            if not current["period"] and re.fullmatch(r"\d{4}/\d{4}", token):
                current["period"] = token
                continue
        current["tokens"].append(token)

    if current["tokens"] or current["period"]:
        sections.append(current)
    return sections


def _decode_taf_section(section: dict, reference: datetime) -> dict:
    wind = ""
    visibility = ""
    weather: list[str] = []
    clouds: list[str] = []
    extras: list[str] = []

    for token in section["tokens"]:
        if re.fullmatch(r"(VRB|\d{3})\d{2,3}(G\d{2,3})?KT", token):
            wind = _decode_taf_wind(token)
        elif token == "CAVOK":
            visibility = "10+ км"
            weather.append("значимых явлений нет")
            clouds.append("облаков ниже 5000 ft нет, видимость 10+ км")
        elif re.fullmatch(r"\d{4}|P6SM|\d+(?:/\d+)?SM", token):
            visibility = _decode_taf_visibility(token)
        elif _decode_taf_cloud(token):
            clouds.append(_decode_taf_cloud(token))
        elif token == "NSW" or re.fullmatch(r"[-+]?(?:VC)?[A-Z]{2,6}", token):
            weather.append(_decode_taf_weather(token))
        elif token.startswith("TX") or token.startswith("TN"):
            extras.append(_decode_taf_temperature_extreme(token, reference) or token)
        elif token.startswith("WS"):
            extras.append(_decode_taf_wind_shear(token) or token)
        else:
            extras.append(token)

    return {
        "label": section["label"],
        "period": section["period"],
        "wind": wind,
        "visibility": visibility,
        "weather": [item for item in weather if item],
        "clouds": [item for item in clouds if item],
        "extras": extras,
        "period_decoded": _decode_taf_section_period(section, reference),
    }


def _decode_taf_section_period(section: dict, reference: datetime) -> str:
    label = section["label"]
    period = section["period"]
    if label == "BASE":
        if not period:
            return ""
        parsed = _parse_taf_period(period, reference)
        if not parsed:
            return period
        start, end = parsed
        return f"{_format_dt_utc(start)} - {_format_dt_utc(end)}"
    if label == "FM" and re.fullmatch(r"\d{6}", period):
        day = int(period[:2])
        hour = int(period[2:4])
        minute = int(period[4:6])
        start = _resolve_taf_day(day, reference).replace(hour=hour, minute=minute)
        return f"с {_format_dt_utc(start)}"
    if period:
        parsed = _parse_taf_period(period, reference)
        if parsed:
            start, end = parsed
            return f"{_format_dt_utc(start)} - {_format_dt_utc(end)}"
    return ""


def decode_taf_raw(icao: str, taf_raw: str) -> Optional[dict]:
    if not taf_raw:
        return None

    tokens = taf_raw.split()
    if len(tokens) < 4 or tokens[0] != "TAF":
        return None

    modifier = ""
    token_index = 1
    if tokens[token_index] in {"AMD", "COR"}:
        modifier = tokens[token_index]
        token_index += 1

    station = tokens[token_index] if len(tokens) > token_index else icao.upper()
    token_index += 1
    issue_token = tokens[token_index] if len(tokens) > token_index else ""
    token_index += 1
    valid_token = tokens[token_index] if len(tokens) > token_index else ""
    token_index += 1

    reference = _taf_reference_date()
    issue_dt = _parse_taf_issue_time(issue_token, reference)
    valid_period = _parse_taf_period(valid_token, issue_dt or reference)
    sections = _split_taf_sections(tokens[token_index:])

    result = {
        "icao": station,
        "airport_name": AIRPORT_NAMES.get(station.upper(), station.upper()),
        "taf_type": "TAF" if not modifier else f"TAF {modifier}",
        "issue_time_raw": issue_token,
        "issue_time": _format_dt_utc(issue_dt) if issue_dt else issue_token,
        "validity_raw": valid_token,
        "validity": (
            f"{_format_dt_utc(valid_period[0])} - {_format_dt_utc(valid_period[1])}"
            if valid_period else valid_token
        ),
        "sections": [],
        "raw_taf": taf_raw,
    }

    base_section = {
        "label": "BASE",
        "period": valid_token,
        "tokens": [],
    }
    if sections and sections[0]["label"] == "BASE":
        base_section = sections[0]
        extra_sections = sections[1:]
    else:
        base_section["tokens"] = tokens[token_index:]
        extra_sections = []

    result["base"] = _decode_taf_section(base_section, issue_dt or reference)
    result["sections"] = [
        _decode_taf_section(section, issue_dt or reference) for section in extra_sections
    ]
    return result
