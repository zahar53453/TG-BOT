import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
METEOFRANCE_APPLICATION_ID = os.getenv("METEOFRANCE_APPLICATION_ID", "").strip()

POLL_INTERVAL = 60

BLICK_POLL_INTERVAL = 600

BLICK = {
    "chat_ids": [],
}

METEOFRANCE_6M = {
    "key": "LFPB_MF_6M",
    "station_id": "95088001",
    "station_name": "Le Bourget Aeroport / LFPB area",
    "chat_ids": [-1003945763334],
    "poll_interval": 60,
}

WUNDERGROUND_PWS = {
    "key": "EDDM_IOBERD38",
    "station_id": "IOBERD38",
    "station_name": "Schwaig / EDDM area",
    "api_key": os.getenv("WUNDERGROUND_PWS_API_KEY", "").strip(),
    "dashboard_url": "https://www.wunderground.com/dashboard/pws/IOBERD38",
    "chat_ids": [-1003996854328],
    "poll_interval": 300,
    "units": "m",
}

ICON_D2 = {
    "chat_ids": [-1003759323040],
}

ICON_FORECASTS = [
    {
        "key": "EDDM_ICON_D2",
        "icao": "EDDM",
        "airport_name": "Muenchen (EDDM)",
        "model": "icon_d2",
        "latitude": 48.3538,
        "longitude": 11.7861,
        "timezone_name": "Europe/Berlin",
        "chat_ids": [-1003759323040],
    },
    {
        "key": "LFPB_ICON_D2",
        "icao": "LFPB",
        "airport_name": "Paris Le Bourget (LFPB)",
        "model": "icon_d2",
        "latitude": 48.9694,
        "longitude": 2.4414,
        "timezone_name": "Europe/Paris",
        "chat_ids": [-1003906745219],
    },
    {
        "key": "EGLC_ICON_D2",
        "icao": "EGLC",
        "airport_name": "London City (EGLC)",
        "model": "icon_d2",
        "latitude": 51.5053,
        "longitude": 0.0553,
        "timezone_name": "Europe/London",
        "chat_ids": [-1003877205563],
    },
    {
        "key": "LEMD_ICON_EU",
        "icao": "LEMD",
        "airport_name": "Madrid Barajas (LEMD)",
        "model": "icon_eu",
        "latitude": 40.4722,
        "longitude": -3.5608,
        "timezone_name": "Europe/Madrid",
        "chat_ids": [-1003828603869],
    },
]

SCANNERS = {
    "EGLC": {
        "icao": "EGLC",
        "chat_ids": [-1003912157606],
        "metar_minutes": [20, 50],
    },
    "LFPB": {
        "icao": "LFPB",
        "chat_ids": [-1003766103504],
        "metar_minutes": [0, 30],
    },
    "LEMD": {
        "icao": "LEMD",
        "chat_ids": [-1003727992542],
        "metar_minutes": [0, 30],
    },
    "EDDM": {
        "icao": "EDDM",
        "chat_ids": [-1003931618915],
        "metar_minutes": [20, 50],
    },
}
