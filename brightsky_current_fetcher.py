"""Fetcher for Bright Sky current SYNOP weather near Munich Airport."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://api.brightsky.dev/current_weather"
_TIMEOUT = 20.0
_RETRIES = 3
_RETRY_SLEEP = 3.0


@dataclass(frozen=True)
class BrightSkyCurrentConfig:
    key: str
    wmo_station_id: str
    station_name: str
    chat_ids: list
    poll_interval: int = 60


@dataclass
class BrightSkyCurrentObservation:
    key: str
    station_name: str
    wmo_station_id: str
    dwd_station_id: str
    source_id: Optional[int]
    observed_at: str
    latitude: Optional[float]
    longitude: Optional[float]
    height_m: Optional[float]
    temperature_c: Optional[float]
    dewpoint_c: Optional[float]
    humidity_pct: Optional[float]
    pressure_msl_hpa: Optional[float]
    cloud_cover_pct: Optional[int]
    condition: str
    icon: str
    visibility_m: Optional[int]
    precipitation_10_mm: Optional[float]
    precipitation_30_mm: Optional[float]
    precipitation_60_mm: Optional[float]
    wind_direction_10_deg: Optional[int]
    wind_direction_30_deg: Optional[int]
    wind_direction_60_deg: Optional[int]
    wind_speed_10_kmh: Optional[float]
    wind_speed_30_kmh: Optional[float]
    wind_speed_60_kmh: Optional[float]
    wind_gust_direction_10_deg: Optional[int]
    wind_gust_speed_10_kmh: Optional[float]
    raw_weather: dict
    raw_source: dict


def _to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_observation(config: BrightSkyCurrentConfig, payload: dict) -> Optional[BrightSkyCurrentObservation]:
    weather = payload.get("weather")
    sources = payload.get("sources")
    if not isinstance(weather, dict):
        return None

    source = sources[0] if isinstance(sources, list) and sources and isinstance(sources[0], dict) else {}
    return BrightSkyCurrentObservation(
        key=config.key,
        station_name=str(source.get("station_name") or config.station_name),
        wmo_station_id=str(source.get("wmo_station_id") or config.wmo_station_id),
        dwd_station_id=str(source.get("dwd_station_id") or ""),
        source_id=_to_int(weather.get("source_id")),
        observed_at=str(weather.get("timestamp") or ""),
        latitude=_to_float(source.get("lat")),
        longitude=_to_float(source.get("lon")),
        height_m=_to_float(source.get("height")),
        temperature_c=_to_float(weather.get("temperature")),
        dewpoint_c=_to_float(weather.get("dew_point")),
        humidity_pct=_to_float(weather.get("relative_humidity")),
        pressure_msl_hpa=_to_float(weather.get("pressure_msl")),
        cloud_cover_pct=_to_int(weather.get("cloud_cover")),
        condition=str(weather.get("condition") or ""),
        icon=str(weather.get("icon") or ""),
        visibility_m=_to_int(weather.get("visibility")),
        precipitation_10_mm=_to_float(weather.get("precipitation_10")),
        precipitation_30_mm=_to_float(weather.get("precipitation_30")),
        precipitation_60_mm=_to_float(weather.get("precipitation_60")),
        wind_direction_10_deg=_to_int(weather.get("wind_direction_10")),
        wind_direction_30_deg=_to_int(weather.get("wind_direction_30")),
        wind_direction_60_deg=_to_int(weather.get("wind_direction_60")),
        wind_speed_10_kmh=_to_float(weather.get("wind_speed_10")),
        wind_speed_30_kmh=_to_float(weather.get("wind_speed_30")),
        wind_speed_60_kmh=_to_float(weather.get("wind_speed_60")),
        wind_gust_direction_10_deg=_to_int(weather.get("wind_gust_direction_10")),
        wind_gust_speed_10_kmh=_to_float(weather.get("wind_gust_speed_10")),
        raw_weather=weather,
        raw_source=source,
    )


def _fetch_sync(config: BrightSkyCurrentConfig) -> Optional[BrightSkyCurrentObservation]:
    for attempt in range(1, _RETRIES + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT, trust_env=False, follow_redirects=True) as client:
                response = client.get(_BASE_URL, params={"wmo_station_id": config.wmo_station_id})
                response.raise_for_status()
                return _parse_observation(config, response.json())
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            log.warning("[%s] Bright Sky network error on attempt %s/%s: %s", config.key, attempt, _RETRIES, exc)
            if attempt < _RETRIES:
                time.sleep(_RETRY_SLEEP)
        except Exception as exc:
            log.warning("[%s] Bright Sky fetch failed: %s", config.key, exc)
            return None
    return None


async def fetch_brightsky_current(
    config: BrightSkyCurrentConfig,
) -> Optional[BrightSkyCurrentObservation]:
    return await asyncio.to_thread(_fetch_sync, config)
