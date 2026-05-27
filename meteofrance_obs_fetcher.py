import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# Конфиг импортируется поздно (чтобы избежать циклических импортов)
def _cfg_application_id() -> str:
    try:
        import config as _cfg
        return getattr(_cfg, "METEOFRANCE_APPLICATION_ID", "").strip()
    except Exception:
        return ""

TOKEN_URL = "https://portail-api.meteofrance.fr/token"
BASE_URL = "https://public-api.meteofrance.fr/public/DPObs"
DEFAULT_STATION_ID = "95088001"  # Le Bourget aeroport / Bonneuil-en-France


@dataclass(frozen=True)
class MeteoFranceObsConfig:
    key: str
    station_id: str
    station_name: str
    chat_ids: list
    poll_interval: int = 60


@dataclass
class MeteoFranceObservation:
    key: str
    station_id: str
    station_name: str
    validity_time: str
    insert_time: str
    reference_time: str
    temp_c: Optional[float]
    dewpoint_c: Optional[float]
    humidity_pct: Optional[float]
    wind_dir_deg: Optional[float]
    wind_speed_ms: Optional[float]
    gust_dir_deg: Optional[float]
    gust_speed_ms: Optional[float]
    precipitation_mm: Optional[float]
    pressure_hpa: Optional[float]
    sea_level_pressure_hpa: Optional[float]
    raw_properties: dict


class MeteoFranceTokenProvider:
    def __init__(self) -> None:
        self._token: str = ""
        self._expires_at: Optional[datetime] = None

    def _direct_token(self) -> str:
        return os.getenv("METEOFRANCE_API_TOKEN", "").strip()

    def _application_id(self) -> str:
        # Приоритет: переменная среды → config.py
        return (
            os.getenv("METEOFRANCE_APPLICATION_ID", "").strip()
            or _cfg_application_id()
        )

    def is_configured(self) -> bool:
        return bool(self._direct_token() or self._application_id())

    def _is_valid(self) -> bool:
        if not self._token or not self._expires_at:
            return False
        return datetime.now(timezone.utc) < self._expires_at

    def get_token(self) -> Optional[str]:
        direct_token = self._direct_token()
        if direct_token:
            return direct_token

        if self._is_valid():
            return self._token

        application_id = self._application_id()
        if not application_id:
            return None

        try:
            with httpx.Client(timeout=20.0, trust_env=False) as client:
                response = client.post(
                    TOKEN_URL,
                    data={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {application_id}"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            log.warning("[MF 6m] token refresh failed: %s", exc)
            return None

        token = payload.get("access_token") or payload.get("token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            log.warning("[MF 6m] token response missing access token")
            return None

        self._token = token
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 120))
        return self._token


_token_provider = MeteoFranceTokenProvider()


def meteofrance_is_configured() -> bool:
    return _token_provider.is_configured()


def _kelvin_to_celsius(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value) - 273.15, 1)


def _pa_to_hpa(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value) / 100.0, 1)


def _parse_observation(config: MeteoFranceObsConfig, payload: object) -> Optional[MeteoFranceObservation]:
    if isinstance(payload, list) and payload:
        feature = payload[0]
    elif isinstance(payload, dict) and payload.get("features"):
        feature = payload["features"][0]
    elif isinstance(payload, dict):
        feature = payload
    else:
        return None

    props = feature.get("properties", feature)
    if not isinstance(props, dict):
        return None

    return MeteoFranceObservation(
        key=config.key,
        station_id=config.station_id,
        station_name=config.station_name,
        validity_time=str(props.get("validity_time", "")),
        insert_time=str(props.get("insert_time", "")),
        reference_time=str(props.get("reference_time", "")),
        temp_c=_kelvin_to_celsius(props.get("t")),
        dewpoint_c=_kelvin_to_celsius(props.get("td")),
        humidity_pct=props.get("u"),
        wind_dir_deg=props.get("dd"),
        wind_speed_ms=props.get("ff"),
        gust_dir_deg=props.get("dxi10"),
        gust_speed_ms=props.get("fxi10"),
        precipitation_mm=props.get("rr_per"),
        pressure_hpa=_pa_to_hpa(props.get("pres")),
        sea_level_pressure_hpa=_pa_to_hpa(props.get("pmer")),
        raw_properties=props,
    )


def _fetch_sync(config: MeteoFranceObsConfig) -> Optional[MeteoFranceObservation]:
    token = _token_provider.get_token()
    if not token:
        log.warning("[MF 6m] application ID not configured or token unavailable")
        return None

    try:
        with httpx.Client(timeout=20.0, trust_env=False) as client:
            response = client.get(
                f"{BASE_URL}/station/infrahoraire-6m",
                params={"id_station": config.station_id, "format": "json"},
                headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
            )
            if response.status_code == 401:
                _token_provider._token = ""
                _token_provider._expires_at = None
                token = _token_provider.get_token()
                if not token:
                    return None
                response = client.get(
                    f"{BASE_URL}/station/infrahoraire-6m",
                    params={"id_station": config.station_id, "format": "json"},
                    headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
                )

            response.raise_for_status()
            return _parse_observation(config, response.json())
    except Exception as exc:
        log.warning("[%s] MF 6m fetch failed: %s", config.key, exc)
        return None


async def fetch_meteofrance_observation(config: MeteoFranceObsConfig) -> Optional[MeteoFranceObservation]:
    return await asyncio.to_thread(_fetch_sync, config)
