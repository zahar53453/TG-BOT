"""Fetcher for OpenWeather One Call 3.0 current conditions."""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"
_TIMEOUT = 20.0
_RETRIES = 3
_RETRY_SLEEP = 3.0


@dataclass(frozen=True)
class OpenWeatherOneCallConfig:
    key: str
    airport_name: str
    latitude: float
    longitude: float
    timezone_name: str
    api_key: str
    chat_ids: list
    poll_interval: int = 60
    units: str = "metric"
    language: str = "ru"


@dataclass
class OpenWeatherCurrentObservation:
    key: str
    airport_name: str
    latitude: float
    longitude: float
    timezone_name: str
    observed_at_unix: int
    observed_at_utc: str
    fetched_at_utc: str
    sunrise_unix: Optional[int]
    sunset_unix: Optional[int]
    temperature_c: Optional[float]
    feels_like_c: Optional[float]
    pressure_hpa: Optional[int]
    humidity_pct: Optional[int]
    dewpoint_c: Optional[float]
    cloudiness_pct: Optional[int]
    visibility_m: Optional[int]
    windspeed_ms: Optional[float]
    windgust_ms: Optional[float]
    winddir_deg: Optional[int]
    weather_main: str
    weather_description: str
    weather_icon: str
    rain_1h_mm: Optional[float]
    snow_1h_mm: Optional[float]
    raw_current: dict


def _cfg_api_key() -> str:
    try:
        import config as _cfg
        return getattr(_cfg, "OPENWEATHER_API_KEY", "").strip()
    except Exception:
        return ""


def _to_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_utc(unix_ts: Optional[int]) -> str:
    if not unix_ts:
        return ""
    return datetime.utcfromtimestamp(unix_ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def openweather_is_configured() -> bool:
    return bool(os.getenv("OPENWEATHER_API_KEY", "").strip() or _cfg_api_key())


def _resolve_api_key(config: OpenWeatherOneCallConfig) -> str:
    return config.api_key.strip() or os.getenv("OPENWEATHER_API_KEY", "").strip() or _cfg_api_key()


def _parse_observation(config: OpenWeatherOneCallConfig, payload: dict) -> Optional[OpenWeatherCurrentObservation]:
    current = payload.get("current")
    if not isinstance(current, dict):
        return None

    weather = current.get("weather")
    first_weather = weather[0] if isinstance(weather, list) and weather else {}
    rain = current.get("rain") if isinstance(current.get("rain"), dict) else {}
    snow = current.get("snow") if isinstance(current.get("snow"), dict) else {}

    observed_at_unix = _to_int(current.get("dt"))
    if not observed_at_unix:
        return None

    return OpenWeatherCurrentObservation(
        key=config.key,
        airport_name=config.airport_name,
        latitude=float(payload.get("lat", config.latitude)),
        longitude=float(payload.get("lon", config.longitude)),
        timezone_name=str(payload.get("timezone") or config.timezone_name),
        observed_at_unix=observed_at_unix,
        observed_at_utc=_fmt_utc(observed_at_unix),
        fetched_at_utc=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        sunrise_unix=_to_int(current.get("sunrise")),
        sunset_unix=_to_int(current.get("sunset")),
        temperature_c=_to_float(current.get("temp")),
        feels_like_c=_to_float(current.get("feels_like")),
        pressure_hpa=_to_int(current.get("pressure")),
        humidity_pct=_to_int(current.get("humidity")),
        dewpoint_c=_to_float(current.get("dew_point")),
        cloudiness_pct=_to_int(current.get("clouds")),
        visibility_m=_to_int(current.get("visibility")),
        windspeed_ms=_to_float(current.get("wind_speed")),
        windgust_ms=_to_float(current.get("wind_gust")),
        winddir_deg=_to_int(current.get("wind_deg")),
        weather_main=str(first_weather.get("main") or ""),
        weather_description=str(first_weather.get("description") or ""),
        weather_icon=str(first_weather.get("icon") or ""),
        rain_1h_mm=_to_float(rain.get("1h")),
        snow_1h_mm=_to_float(snow.get("1h")),
        raw_current=current,
    )


def _fetch_sync(config: OpenWeatherOneCallConfig) -> Optional[OpenWeatherCurrentObservation]:
    api_key = _resolve_api_key(config)
    if not api_key:
        log.warning("[%s] OpenWeather API key is not configured", config.key)
        return None

    params = {
        "lat": config.latitude,
        "lon": config.longitude,
        "appid": api_key,
        "units": config.units,
        "lang": config.language,
        "exclude": "minutely,hourly,daily,alerts",
    }

    for attempt in range(1, _RETRIES + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT, trust_env=False, follow_redirects=True) as client:
                response = client.get(_BASE_URL, params=params)
                response.raise_for_status()
                return _parse_observation(config, response.json())
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            log.warning(
                "[%s] OpenWeather network error on attempt %s/%s: %s",
                config.key,
                attempt,
                _RETRIES,
                exc,
            )
            if attempt < _RETRIES:
                time.sleep(_RETRY_SLEEP)
        except Exception as exc:
            log.warning("[%s] OpenWeather fetch failed: %s", config.key, exc)
            return None
    return None


async def fetch_openweather_current(
    config: OpenWeatherOneCallConfig,
) -> Optional[OpenWeatherCurrentObservation]:
    return await asyncio.to_thread(_fetch_sync, config)
