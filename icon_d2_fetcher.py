"""
Generic ICON forecast fetcher for multiple airports/models.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

MODEL_RUN_HOURS = [0, 3, 6, 9, 12, 15, 18, 21]
MODEL_DELAY_MIN = 75


@dataclass(frozen=True)
class IconModelConfig:
    key: str
    icao: str
    airport_name: str
    model: str
    latitude: float
    longitude: float
    timezone_name: str
    chat_ids: list
    model_delay_min: int = MODEL_DELAY_MIN


@dataclass
class IconD2Forecast:
    key: str = ""
    icao: str = ""
    airport_name: str = ""
    model: str = ""
    timezone_name: str = ""
    model_run_utc: str = ""
    fetched_at: str = ""
    fingerprint: str = ""

    times: list = field(default_factory=list)
    temps: list = field(default_factory=list)
    winds: list = field(default_factory=list)
    wind_dirs: list = field(default_factory=list)
    precips: list = field(default_factory=list)
    weather_codes: list = field(default_factory=list)
    clouds: list = field(default_factory=list)

    elevation: float = 0.0


_WMO_RU = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    61: "слабый дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "слабый снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "ливень",
    81: "ливни",
    82: "сильный ливень",
    85: "снежный ливень",
    86: "сильный снежный ливень",
    95: "гроза",
    96: "гроза с градом",
    99: "гроза с сильным градом",
}


def wmo_to_ru(code) -> str:
    return _WMO_RU.get(code, f"код {code}")


def _make_fingerprint(temps: list) -> str:
    rounded = [round(t, 1) for t in temps[:48] if t is not None]
    return hashlib.md5(str(rounded).encode()).hexdigest()


def _build_url(config: IconModelConfig) -> str:
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={config.latitude}&longitude={config.longitude}"
        "&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,"
        "precipitation,weather_code,cloud_cover"
        f"&models={config.model}"
        "&forecast_days=2"
        f"&timezone={config.timezone_name.replace('/', '%2F')}"
        "&timeformat=iso8601"
        "&wind_speed_unit=kmh"
    )


def _infer_model_run(now_utc: datetime, delay_minutes: int) -> str:
    best_run: Optional[datetime] = None
    for days_back in range(2):
        base = (now_utc - timedelta(days=days_back)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        for run_hour in MODEL_RUN_HOURS:
            run_time = base + timedelta(hours=run_hour)
            avail_time = run_time + timedelta(minutes=delay_minutes)
            if avail_time <= now_utc and (best_run is None or run_time > best_run):
                best_run = run_time
    if not best_run:
        return ""
    return best_run.strftime("%Y-%m-%dT%H:%M") + "Z"


def _parse_response(config: IconModelConfig, data: dict) -> IconD2Forecast:
    now_utc = datetime.now(timezone.utc)
    hourly = data.get("hourly", {})
    temps = hourly.get("temperature_2m", [])
    times = hourly.get("time", [])

    return IconD2Forecast(
        key=config.key,
        icao=config.icao,
        airport_name=config.airport_name,
        model=config.model,
        timezone_name=config.timezone_name,
        model_run_utc=_infer_model_run(now_utc, config.model_delay_min),
        fetched_at=now_utc.strftime("%Y-%m-%dT%H:%M") + "Z",
        fingerprint=_make_fingerprint(temps),
        times=times,
        temps=temps,
        winds=hourly.get("wind_speed_10m", []),
        wind_dirs=hourly.get("wind_direction_10m", []),
        precips=hourly.get("precipitation", []),
        weather_codes=hourly.get("weather_code", []),
        clouds=hourly.get("cloud_cover", []),
        elevation=data.get("elevation", 0.0),
    )


_ICON_RETRIES = 3
_ICON_RETRY_SLEEP = 5.0


def _fetch_sync(config: IconModelConfig) -> Optional[IconD2Forecast]:
    import time
    for attempt in range(1, _ICON_RETRIES + 1):
        try:
            with httpx.Client(timeout=20.0, trust_env=False) as client:
                response = client.get(_build_url(config))
                if response.status_code != 200:
                    log.warning("[%s] ICON HTTP %s", config.key, response.status_code)
                    return None
                return _parse_response(config, response.json())
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout) as exc:
            log.warning("[%s] ICON network error on attempt %s/%s: %s", config.key, attempt, _ICON_RETRIES, exc)
            if attempt < _ICON_RETRIES:
                time.sleep(_ICON_RETRY_SLEEP)
        except httpx.RequestError as exc:
            log.warning("[%s] ICON network error: %s", config.key, exc)
            return None
        except Exception as exc:
            log.error("[%s] ICON unexpected error: %s", config.key, exc, exc_info=True)
            return None
    return None


async def fetch_icon_forecast(config: IconModelConfig) -> Optional[IconD2Forecast]:
    return await asyncio.to_thread(_fetch_sync, config)


async def fetch_icon_d2() -> Optional[IconD2Forecast]:
    """Backward-compatible wrapper for old single-EDDM usage."""
    default = IconModelConfig(
        key="EDDM_ICON_D2",
        icao="EDDM",
        airport_name="Мюнхен (EDDM)",
        model="icon_d2",
        latitude=48.3538,
        longitude=11.7861,
        timezone_name="Europe/Berlin",
        chat_ids=[],
    )
    return await fetch_icon_forecast(default)


def secs_until_next_run(delay_minutes: int = MODEL_DELAY_MIN) -> float:
    now = datetime.now(timezone.utc)
    next_avail = None
    for run_hour in MODEL_RUN_HOURS:
        for day_offset in [0, 1]:
            candidate = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
            candidate += timedelta(days=day_offset, minutes=delay_minutes)
            if candidate > now and (next_avail is None or candidate < next_avail):
                next_avail = candidate
    delta = (next_avail - now).total_seconds() if next_avail else 3600
    return max(60.0, delta)
