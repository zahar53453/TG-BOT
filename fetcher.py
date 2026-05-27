"""
Weather data fetchers.

- fetch_weather()    -> AirportWeather/Meandair nowcast data
- fetch_metar_noaa() -> official METAR from Aviation Weather Center
- fetch_taf_noaa()   -> official TAF from Aviation Weather Center
"""

import asyncio
from typing import Optional

import httpx

_AW_BASE = "https://server.airportweather.com"
_AW_HEADERS = {
    "x-fingerprint": "tgbot-metar-monitor-v1",
    "Origin": "https://airportweather.com",
    "Referer": "https://airportweather.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_NOAA_BASE = "https://aviationweather.gov/api/data"
_NOAA_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=10.0, pool=10.0)
_NOAA_RETRIES = 3
_NOAA_RETRY_SLEEP = 3.0  # секунды между попытками


def _fetch_weather_sync(icao: str) -> Optional[dict]:
    url = f"{_AW_BASE}/api/airports/{icao.upper()}/weather"
    try:
        with httpx.Client(timeout=15.0, headers=_AW_HEADERS, follow_redirects=True, trust_env=False) as client:
            response = client.get(url)
            if response.status_code == 200:
                return response.json()
            print(f"[{icao}] AW HTTP {response.status_code}")
    except httpx.RequestError as exc:
        print(f"[{icao}] AW network error: {exc}")
    except Exception as exc:
        print(f"[{icao}] AW error: {exc}")
    return None


def _fetch_metar_noaa_sync(icao: str) -> Optional[dict]:
    """Return the freshest METAR from AWC (with retries)."""
    import time
    for attempt in range(1, _NOAA_RETRIES + 1):
        try:
            with httpx.Client(timeout=_NOAA_TIMEOUT, follow_redirects=True, trust_env=False) as client:
                response = client.get(
                    f"{_NOAA_BASE}/metar",
                    params={"ids": icao.upper(), "format": "json", "hours": 1},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                print(f"[{icao}] METAR HTTP {response.status_code}")
                return None
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            print(f"[{icao}] METAR network error on attempt {attempt}/{_NOAA_RETRIES}: {exc}")
            if attempt < _NOAA_RETRIES:
                time.sleep(_NOAA_RETRY_SLEEP)
        except Exception as exc:
            print(f"[{icao}] METAR error: {exc}")
            return None
    return None


def _fetch_taf_noaa_sync(icao: str) -> Optional[str]:
    """Return the current TAF in raw format from AWC (with retries)."""
    import time
    for attempt in range(1, _NOAA_RETRIES + 1):
        try:
            with httpx.Client(timeout=_NOAA_TIMEOUT, follow_redirects=True, trust_env=False) as client:
                response = client.get(
                    f"{_NOAA_BASE}/taf",
                    params={"ids": icao.upper(), "format": "raw"},
                )
                if response.status_code == 200:
                    text = " ".join(response.text.split())
                    if not text or "No data found" in text:
                        return None
                    return text
                print(f"[{icao}] TAF HTTP {response.status_code}")
                return None
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            print(f"[{icao}] TAF network error on attempt {attempt}/{_NOAA_RETRIES}: {exc}")
            if attempt < _NOAA_RETRIES:
                time.sleep(_NOAA_RETRY_SLEEP)
        except Exception as exc:
            print(f"[{icao}] TAF error: {exc}")
            return None
    return None


async def fetch_weather(icao: str) -> Optional[dict]:
    return await asyncio.to_thread(_fetch_weather_sync, icao)


async def fetch_metar_noaa(icao: str) -> Optional[dict]:
    return await asyncio.to_thread(_fetch_metar_noaa_sync, icao)


async def fetch_taf_noaa(icao: str) -> Optional[str]:
    return await asyncio.to_thread(_fetch_taf_noaa_sync, icao)
