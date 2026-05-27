"""Fetcher for Weather Underground Personal Weather Station observations."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://api.weather.com/v2/pws/observations/all/1day"
_TIMEOUT = 20.0
_RETRIES = 3
_RETRY_SLEEP = 3.0


@dataclass(frozen=True)
class WundergroundPwsConfig:
    key: str
    station_id: str
    station_name: str
    api_key: str
    dashboard_url: str
    chat_ids: list
    poll_interval: int = 300
    units: str = "m"


@dataclass
class WundergroundPwsObservation:
    key: str
    station_id: str
    station_name: str
    dashboard_url: str
    observed_at_utc: str
    observed_at_local: str
    timezone_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    temperature_c: Optional[float]
    dewpoint_c: Optional[float]
    humidity_pct: Optional[float]
    windspeed_ms: Optional[float]
    windgust_ms: Optional[float]
    winddir_deg: Optional[float]
    pressure_hpa: Optional[float]
    pressure_trend_hpa: Optional[float]
    precip_rate_mm_h: Optional[float]
    precip_total_mm: Optional[float]
    uv_index: Optional[float]
    solar_radiation_wm2: Optional[float]
    qc_status: Optional[int]
    raw_observation: dict


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


def _pick_metric_bucket(observation: dict) -> dict:
    if isinstance(observation.get("metric"), dict):
        return observation["metric"]
    if isinstance(observation.get("imperial"), dict):
        return observation["imperial"]
    return {}


def _parse_observation(config: WundergroundPwsConfig, payload: dict) -> Optional[WundergroundPwsObservation]:
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        return None

    latest = max(
        (item for item in observations if isinstance(item, dict)),
        key=lambda item: item.get("epoch", 0),
        default=None,
    )
    if not latest:
        return None

    metrics = _pick_metric_bucket(latest)
    return WundergroundPwsObservation(
        key=config.key,
        station_id=str(latest.get("stationID") or config.station_id),
        station_name=config.station_name,
        dashboard_url=config.dashboard_url,
        observed_at_utc=str(latest.get("obsTimeUtc") or ""),
        observed_at_local=str(latest.get("obsTimeLocal") or ""),
        timezone_name=str(latest.get("tz") or ""),
        latitude=_to_float(latest.get("lat")),
        longitude=_to_float(latest.get("lon")),
        temperature_c=_to_float(metrics.get("tempAvg")),
        dewpoint_c=_to_float(metrics.get("dewptAvg")),
        humidity_pct=_to_float(latest.get("humidityAvg")),
        windspeed_ms=_to_float(metrics.get("windspeedAvg")),
        windgust_ms=_to_float(metrics.get("windgustHigh")),
        winddir_deg=_to_float(latest.get("winddirAvg")),
        pressure_hpa=_to_float(metrics.get("pressureMax")),
        pressure_trend_hpa=_to_float(metrics.get("pressureTrend")),
        precip_rate_mm_h=_to_float(metrics.get("precipRate")),
        precip_total_mm=_to_float(metrics.get("precipTotal")),
        uv_index=_to_float(latest.get("uvHigh")),
        solar_radiation_wm2=_to_float(latest.get("solarRadiationHigh")),
        qc_status=_to_int(latest.get("qcStatus")),
        raw_observation=latest,
    )


def _fetch_sync(config: WundergroundPwsConfig) -> Optional[WundergroundPwsObservation]:
    params = {
        "apiKey": config.api_key,
        "stationId": config.station_id,
        "numericPrecision": "decimal",
        "format": "json",
        "units": config.units,
    }

    for attempt in range(1, _RETRIES + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT, trust_env=False, follow_redirects=True) as client:
                response = client.get(_BASE_URL, params=params)
                response.raise_for_status()
                return _parse_observation(config, response.json())
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            log.warning("[%s] WU PWS network error on attempt %s/%s: %s", config.key, attempt, _RETRIES, exc)
            if attempt < _RETRIES:
                time.sleep(_RETRY_SLEEP)
        except Exception as exc:
            log.warning("[%s] WU PWS fetch failed: %s", config.key, exc)
            return None
    return None


async def fetch_wunderground_pws_observation(
    config: WundergroundPwsConfig,
) -> Optional[WundergroundPwsObservation]:
    return await asyncio.to_thread(_fetch_sync, config)
