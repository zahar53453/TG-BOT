"""In-memory state used to deduplicate notifications."""

_last_aw_metar: dict[str, str] = {}
_last_metar_report_time: dict[str, str] = {}
_last_taf_raw: dict[str, str] = {}
_last_blick: dict = {}
_last_icon_forecast_fingerprints: dict[str, str] = {}
_last_meteofrance_obs_validity: dict[str, str] = {}
_last_wunderground_obs_time: dict[str, str] = {}
_last_openweather_obs_time: dict[str, int] = {}


def is_updated(icao: str, aw_metar_str: str) -> bool:
    key = icao.upper()
    if _last_aw_metar.get(key) != aw_metar_str:
        _last_aw_metar[key] = aw_metar_str
        return True
    return False


def mark_seen(icao: str, aw_metar_str: str) -> None:
    _last_aw_metar[icao.upper()] = aw_metar_str


def is_new_metar(icao: str, report_time: str) -> bool:
    key = icao.upper()
    return _last_metar_report_time.get(key) != report_time


def mark_metar_seen(icao: str, report_time: str) -> None:
    _last_metar_report_time[icao.upper()] = report_time


def is_new_taf(icao: str, taf_raw: str) -> bool:
    key = icao.upper()
    return _last_taf_raw.get(key) != taf_raw


def mark_taf_seen(icao: str, taf_raw: str) -> None:
    _last_taf_raw[icao.upper()] = taf_raw


def is_new_meteofrance_obs(key: str, validity_time: str) -> bool:
    return _last_meteofrance_obs_validity.get(key) != validity_time


def init_meteofrance_obs(key: str, validity_time: str) -> None:
    _last_meteofrance_obs_validity[key] = validity_time


def is_blick_updated(snapshot: dict) -> bool:
    global _last_blick
    if _last_blick != snapshot:
        _last_blick = snapshot.copy()
        return True
    return False


def init_blick(snapshot: dict) -> None:
    global _last_blick
    _last_blick = snapshot.copy()


def is_icon_d2_new(key: str, fingerprint: str) -> bool:
    return _last_icon_forecast_fingerprints.get(key) != fingerprint


def init_icon_d2(key: str, fingerprint: str) -> None:
    _last_icon_forecast_fingerprints[key] = fingerprint


def is_new_wunderground_observation(key: str, observed_at_utc: str) -> bool:
    return _last_wunderground_obs_time.get(key) != observed_at_utc


def init_wunderground_observation(key: str, observed_at_utc: str) -> None:
    _last_wunderground_obs_time[key] = observed_at_utc


def is_new_openweather_observation(key: str, observed_at_unix: int) -> bool:
    return _last_openweather_obs_time.get(key) != observed_at_unix


def init_openweather_observation(key: str, observed_at_unix: int) -> None:
    _last_openweather_obs_time[key] = observed_at_unix
