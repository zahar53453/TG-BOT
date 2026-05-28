"""Main scanner runtime."""

import asyncio
import dataclasses
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

import config as cfg
from blick_fetcher import fetch_blick
from blick_formatter import build_blick_message
from fetcher import fetch_metar_noaa, fetch_taf_noaa
from formatter import build_metar_message, build_taf_message
from meteofrance_obs_fetcher import (
    MeteoFranceObsConfig,
    fetch_meteofrance_observation,
    meteofrance_is_configured,
)
from meteofrance_obs_formatter import build_meteofrance_obs_message
from icon_d2_fetcher import IconModelConfig, fetch_icon_forecast, secs_until_next_run
from icon_d2_formatter import build_icon_d2_message
from wunderground_pws_fetcher import (
    WundergroundPwsConfig,
    fetch_wunderground_pws_observation,
)
from wunderground_pws_formatter import build_wunderground_pws_message
from openweather_onecall_fetcher import (
    OpenWeatherOneCallConfig,
    fetch_openweather_current,
)
from openweather_onecall_formatter import build_openweather_current_message
from storage import (
    init_blick,
    init_icon_d2,
    init_openweather_observation,
    init_wunderground_observation,
    is_blick_updated,
    is_icon_d2_new,
    is_new_openweather_observation,
    is_new_wunderground_observation,
    is_new_metar,
    is_new_meteofrance_obs,
    is_new_taf,
    mark_metar_seen,
    mark_taf_seen,
    init_meteofrance_obs,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TAF_POLL_INTERVAL = 300
TELEGRAM_AUTH_RETRIES = 4
TELEGRAM_SEND_RETRIES = 3


class NoEnvHTTPXRequest(HTTPXRequest):
    """PTB request class that ignores system proxy settings."""

    def _build_client(self) -> httpx.AsyncClient:
        kwargs = dict(self._client_kwargs)
        kwargs["trust_env"] = False
        return httpx.AsyncClient(**kwargs)


@dataclass
class ScannerConfig:
    icao: str
    chat_ids: list
    metar_minutes: list


def _in_metar_window(now: datetime, metar_minutes: list) -> bool:
    minute = now.minute
    for expected in metar_minutes:
        window_start = (expected - 1) % 60
        window_end = (expected + 10) % 60
        if window_start <= window_end:
            if window_start <= minute <= window_end:
                return True
        else:
            if minute >= window_start or minute <= window_end:
                return True
    return False


def _secs_until_next_metar_window(now: datetime, metar_minutes: list) -> float:
    if _in_metar_window(now, metar_minutes):
        return 0.0

    minute = now.minute
    second = now.second
    min_wait = float("inf")
    for expected in metar_minutes:
        window_start = (expected - 1) % 60
        wait_minutes = (window_start - minute) % 60
        wait_seconds = wait_minutes * 60 - second
        min_wait = min(min_wait, wait_seconds)
    return max(min_wait, 1.0)


def _seconds_until_next_taf_poll(now: datetime) -> float:
    interval_minutes = TAF_POLL_INTERVAL // 60
    remainder = now.minute % interval_minutes
    wait_minutes = interval_minutes - remainder
    if wait_minutes == interval_minutes:
        wait_minutes = 0
    wait_seconds = wait_minutes * 60 - now.second
    if wait_seconds <= 0:
        wait_seconds += TAF_POLL_INTERVAL
    return max(30.0, float(wait_seconds))


async def send_to_all(bot: Bot, text: str, chat_ids: list) -> bool:
    all_sent = True
    for chat_id in chat_ids:
        sent = False
        for attempt in range(1, TELEGRAM_SEND_RETRIES + 1):
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                log.info(f"  sent to chat {chat_id}")
                sent = True
                break
            except TelegramError as exc:
                log.error(f"  Telegram {chat_id} attempt {attempt}/{TELEGRAM_SEND_RETRIES}: {exc}")
            except Exception as exc:
                log.error(f"  Error {chat_id} attempt {attempt}/{TELEGRAM_SEND_RETRIES}: {exc}")
            if attempt < TELEGRAM_SEND_RETRIES:
                await asyncio.sleep(3)
        if not sent:
            all_sent = False
    return all_sent


def _build_telegram_request(pool_size: int) -> HTTPXRequest:
    _sanitize_proxy_env()
    return NoEnvHTTPXRequest(
        connection_pool_size=pool_size,
        pool_timeout=30.0,
        connect_timeout=20.0,
        read_timeout=40.0,
        write_timeout=40.0,
    )


def _sanitize_proxy_env() -> None:
    """
    httpx/PTB падает на proxy URL вида socks4://...
    Если такой прокси подхвачен из окружения, лучше явно отключить его
    для процесса бота, чем падать на старте.
    """
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        value = os.environ.get(key, "").strip()
        if value.lower().startswith("socks4://"):
            log.warning("Ignoring unsupported proxy from %s: %s", key, value)
            os.environ.pop(key, None)


async def _authorize_bot(bot: Bot) -> Optional[object]:
    last_exc: Optional[Exception] = None
    for attempt in range(1, TELEGRAM_AUTH_RETRIES + 1):
        try:
            return await bot.get_me()
        except TelegramError as exc:
            last_exc = exc
            log.warning(
                "Telegram authorization attempt %s/%s failed: %s",
                attempt,
                TELEGRAM_AUTH_RETRIES,
                exc,
            )
        except Exception as exc:
            last_exc = exc
            log.warning(
                "Telegram authorization attempt %s/%s failed: %s",
                attempt,
                TELEGRAM_AUTH_RETRIES,
                exc,
            )
        if attempt < TELEGRAM_AUTH_RETRIES:
            await asyncio.sleep(5)

    if last_exc:
        log.error("Authorization error after %s attempts: %s", TELEGRAM_AUTH_RETRIES, last_exc)
    return None


async def metar_loop(bot: Bot, sc: ScannerConfig) -> None:
    icao = sc.icao
    metar_minutes = sc.metar_minutes
    log.info(f"[{icao}] METAR loop started (window around {metar_minutes} UTC)")

    data = await fetch_metar_noaa(icao)
    if data:
        report_time = data.get("reportTime", "")
        message = build_metar_message(icao, data)
        sent = True
        if message:
            sent = await send_to_all(bot, message, sc.chat_ids)
        if sent:
            mark_metar_seen(icao, report_time)
            log.info(f"[{icao}] METAR init sent: {report_time or 'N/A'}")
        else:
            log.warning(f"[{icao}] METAR init detected but not fully delivered")
    else:
        log.warning(f"[{icao}] METAR init: no data")

    while True:
        now = datetime.now(timezone.utc)
        if not _in_metar_window(now, metar_minutes):
            wait = _secs_until_next_metar_window(now, metar_minutes)
            log.info(f"[{icao}] METAR next window in {int(wait // 60)}m {int(wait % 60)}s")
            await asyncio.sleep(wait)
            continue

        log.info(f"[{icao}] METAR active window (:{now.minute:02d} UTC)")
        got_new = False

        for _ in range(15):
            data = await fetch_metar_noaa(icao)
            if data:
                report_time = data.get("reportTime", "")
                if is_new_metar(icao, report_time):
                    log.info(f"[{icao}] new METAR: {report_time}")
                    message = build_metar_message(icao, data)
                    sent = True
                    if message:
                        sent = await send_to_all(bot, message, sc.chat_ids)
                    if sent:
                        mark_metar_seen(icao, report_time)
                        got_new = True
                    else:
                        log.warning(f"[{icao}] METAR detected but not fully delivered, will retry")
                else:
                    log.debug(f"[{icao}] METAR unchanged: {report_time}")
            else:
                log.warning(f"[{icao}] METAR: no data from AWC")

            if got_new:
                break
            if not _in_metar_window(datetime.now(timezone.utc), metar_minutes):
                log.info(f"[{icao}] METAR window closed without update")
                break
            await asyncio.sleep(60)

        while _in_metar_window(datetime.now(timezone.utc), metar_minutes):
            await asyncio.sleep(30)

        wait = _secs_until_next_metar_window(datetime.now(timezone.utc), metar_minutes)
        log.info(f"[{icao}] METAR next window in {int(wait // 60)}m {int(wait % 60)}s")
        await asyncio.sleep(wait)


async def taf_loop(bot: Bot, sc: ScannerConfig) -> None:
    icao = sc.icao
    log.info(
        f"[{icao}] TAF loop started "
        f"(poll every {TAF_POLL_INTERVAL // 60} min; routine 00/06/12/18 UTC, AMD/COR anytime)"
    )

    taf_raw = await fetch_taf_noaa(icao)
    if taf_raw:
        try:
            message = build_taf_message(icao, taf_raw)
        except Exception as exc:
            log.exception(f"[{icao}] TAF init parse failed: {exc}")
            message = None
        sent = True
        if message:
            sent = await send_to_all(bot, message, sc.chat_ids)
        if sent:
            mark_taf_seen(icao, taf_raw)
            log.info(f"[{icao}] TAF init sent")
        else:
            log.warning(f"[{icao}] TAF init detected but not fully delivered")
    else:
        log.warning(f"[{icao}] TAF init: no data")

    while True:
        wait = _seconds_until_next_taf_poll(datetime.now(timezone.utc))
        await asyncio.sleep(wait)
        log.info(f"[{icao}] TAF poll ({datetime.now(timezone.utc).strftime('%H:%M:%S UTC')})")

        taf_raw = await fetch_taf_noaa(icao)
        if not taf_raw:
            log.warning(f"[{icao}] TAF: no data")
            continue

        if is_new_taf(icao, taf_raw):
            log.info(f"[{icao}] new TAF detected")
            try:
                message = build_taf_message(icao, taf_raw)
            except Exception as exc:
                log.exception(f"[{icao}] TAF parse failed: {exc}")
                continue
            sent = True
            if message:
                sent = await send_to_all(bot, message, sc.chat_ids)
            if sent:
                mark_taf_seen(icao, taf_raw)
            else:
                log.warning(f"[{icao}] TAF detected but not fully delivered, will retry")
        else:
            log.debug(f"[{icao}] TAF unchanged")


async def blick_loop(bot: Bot) -> None:
    chat_ids = cfg.BLICK.get("chat_ids", [])
    interval = getattr(cfg, "BLICK_POLL_INTERVAL", 600)

    if not chat_ids:
        log.warning("[Blick] chat_ids not configured")
        return

    log.info(f"[Blick] loop started (interval {interval}s, chats: {chat_ids})")

    data = await fetch_blick()
    if data:
        init_blick(dataclasses.asdict(data))
        log.info(f"[Blick] init OK: {data.datetime_str}, T={data.temp}C, wind {data.gust} km/h")
    else:
        log.warning("[Blick] init: no data")

    while True:
        await asyncio.sleep(interval)
        log.info(f"[Blick] poll ({datetime.now(timezone.utc).strftime('%H:%M:%S UTC')})")

        data = await fetch_blick()
        if not data:
            log.warning("[Blick] no data")
            continue

        snapshot = dataclasses.asdict(data)
        if is_blick_updated(snapshot):
            log.info(f"[Blick] new measurement: {data.datetime_str}, T={data.temp}C")
            message = build_blick_message(data)
            await send_to_all(bot, message, chat_ids)
        else:
            log.debug("[Blick] unchanged")


def _meteofrance_config() -> Optional[MeteoFranceObsConfig]:
    raw = getattr(cfg, "METEOFRANCE_6M", None)
    if not raw or not raw.get("chat_ids"):
        return None
    return MeteoFranceObsConfig(**raw)


async def meteofrance_obs_loop(bot: Bot) -> None:
    mf_cfg = _meteofrance_config()
    if not mf_cfg:
        log.warning("[MF 6m] chat_ids not configured")
        return
    if not meteofrance_is_configured():
        log.warning("[MF 6m] METEOFRANCE_APPLICATION_ID is not configured")
        return

    log.info("[MF 6m] loop started for station %s (poll every %ss)", mf_cfg.station_id, mf_cfg.poll_interval)

    observation = await fetch_meteofrance_observation(mf_cfg)
    if observation:
        message = build_meteofrance_obs_message(observation)
        sent = await send_to_all(bot, message, mf_cfg.chat_ids)
        if sent:
            init_meteofrance_obs(mf_cfg.key, observation.validity_time)
            log.info("[MF 6m] init sent: %s", observation.validity_time)
        else:
            log.warning("[MF 6m] init detected but not fully delivered")
    else:
        log.warning("[MF 6m] init: no data")

    while True:
        await asyncio.sleep(mf_cfg.poll_interval)
        observation = await fetch_meteofrance_observation(mf_cfg)
        if not observation:
            log.warning("[MF 6m] no data")
            continue
        if is_new_meteofrance_obs(mf_cfg.key, observation.validity_time):
            message = build_meteofrance_obs_message(observation)
            sent = await send_to_all(bot, message, mf_cfg.chat_ids)
            if sent:
                init_meteofrance_obs(mf_cfg.key, observation.validity_time)
                log.info("[MF 6m] new observation: %s", observation.validity_time)
            else:
                log.warning("[MF 6m] new observation detected but not fully delivered, will retry")
        else:
            log.debug("[MF 6m] unchanged")


def _icon_configs() -> list[IconModelConfig]:
    configs = []
    for item in getattr(cfg, "ICON_FORECASTS", []):
        if item.get("chat_ids"):
            configs.append(IconModelConfig(**item))
    return configs


def _wunderground_pws_config() -> Optional[WundergroundPwsConfig]:
    raw = getattr(cfg, "WUNDERGROUND_PWS", None)
    if not raw or not raw.get("chat_ids") or not raw.get("api_key"):
        return None
    return WundergroundPwsConfig(**raw)


def _openweather_onecall_config() -> Optional[OpenWeatherOneCallConfig]:
    raw = getattr(cfg, "OPENWEATHER_ONECALL", None)
    if not raw or not raw.get("chat_ids") or not raw.get("api_key"):
        return None
    return OpenWeatherOneCallConfig(**raw)


async def _icon_forecast_loop(bot: Bot, icon_cfg: IconModelConfig) -> None:
    log.info("[%s] ICON loop started (%s, chats: %s)", icon_cfg.key, icon_cfg.model, icon_cfg.chat_ids)

    forecast = await fetch_icon_forecast(icon_cfg)
    if forecast:
        log.info("[%s] ICON init OK: run=%s, fp=%s", icon_cfg.key, forecast.model_run_utc, forecast.fingerprint[:8])
        message = build_icon_d2_message(forecast)
        sent = await send_to_all(bot, message, icon_cfg.chat_ids)
        if sent:
            init_icon_d2(icon_cfg.key, forecast.fingerprint)
        else:
            log.warning("[%s] ICON init detected but not fully delivered", icon_cfg.key)
    else:
        log.warning("[%s] ICON init: no data", icon_cfg.key)

    while True:
        wait = secs_until_next_run(icon_cfg.model_delay_min)
        hours, remainder = divmod(int(wait), 3600)
        log.info("[%s] ICON next run in %sh %sm", icon_cfg.key, hours, remainder // 60)
        await asyncio.sleep(wait)

        for attempt in range(10):
            log.info("[%s] ICON poll %s/10 (%s)", icon_cfg.key, attempt + 1, datetime.now(timezone.utc).strftime('%H:%M:%S UTC'))
            forecast = await fetch_icon_forecast(icon_cfg)
            if forecast and is_icon_d2_new(icon_cfg.key, forecast.fingerprint):
                log.info("[%s] ICON new run: %s", icon_cfg.key, forecast.model_run_utc)
                message = build_icon_d2_message(forecast)
                sent = await send_to_all(bot, message, icon_cfg.chat_ids)
                if sent:
                    init_icon_d2(icon_cfg.key, forecast.fingerprint)
                    break
                log.warning("[%s] ICON detected but not fully delivered, will retry", icon_cfg.key)
            if forecast:
                log.debug("[%s] ICON data not updated yet (fp=%s)", icon_cfg.key, forecast.fingerprint[:8])
            else:
                log.warning("[%s] ICON no data", icon_cfg.key)
            await asyncio.sleep(120)


async def icon_d2_loop(bot: Bot) -> None:
    configs = _icon_configs()
    if not configs:
        log.warning("[ICON] no forecast chats configured")
        return
    await asyncio.gather(*[_icon_forecast_loop(bot, icon_cfg) for icon_cfg in configs])


async def wunderground_pws_loop(bot: Bot) -> None:
    wu_cfg = _wunderground_pws_config()
    if not wu_cfg:
        log.warning("[WU PWS] chat_ids not configured")
        return

    log.info(
        "[WU PWS] loop started for %s (poll every %ss, chats: %s)",
        wu_cfg.station_id,
        wu_cfg.poll_interval,
        wu_cfg.chat_ids,
    )

    observation = await fetch_wunderground_pws_observation(wu_cfg)
    if observation:
        message = build_wunderground_pws_message(observation)
        sent = await send_to_all(bot, message, wu_cfg.chat_ids)
        if sent:
            init_wunderground_observation(wu_cfg.key, observation.observed_at_utc)
            log.info("[WU PWS] init sent: %s", observation.observed_at_utc)
        else:
            log.warning("[WU PWS] init detected but not fully delivered")
    else:
        log.warning("[WU PWS] init: no data")

    while True:
        await asyncio.sleep(wu_cfg.poll_interval)
        observation = await fetch_wunderground_pws_observation(wu_cfg)
        if not observation:
            log.warning("[WU PWS] no data")
            continue
        if is_new_wunderground_observation(wu_cfg.key, observation.observed_at_utc):
            message = build_wunderground_pws_message(observation)
            sent = await send_to_all(bot, message, wu_cfg.chat_ids)
            if sent:
                init_wunderground_observation(wu_cfg.key, observation.observed_at_utc)
                log.info("[WU PWS] new observation: %s", observation.observed_at_utc)
            else:
                log.warning("[WU PWS] new observation detected but not fully delivered, will retry")
        else:
            log.debug("[WU PWS] unchanged")


async def openweather_onecall_loop(bot: Bot) -> None:
    ow_cfg = _openweather_onecall_config()
    if not ow_cfg:
        log.warning("[OWM] chat_ids/api_key not configured")
        return

    log.info(
        "[OWM] loop started for %s (poll every %ss, chats: %s)",
        ow_cfg.airport_name,
        ow_cfg.poll_interval,
        ow_cfg.chat_ids,
    )

    observation = await fetch_openweather_current(ow_cfg)
    if observation:
        message = build_openweather_current_message(observation)
        sent = await send_to_all(bot, message, ow_cfg.chat_ids)
        if sent:
            init_openweather_observation(ow_cfg.key, observation.observed_at_unix)
            log.info("[OWM] init sent: %s", observation.observed_at_utc)
        else:
            log.warning("[OWM] init detected but not fully delivered")
    else:
        log.warning("[OWM] init: no data")

    while True:
        await asyncio.sleep(ow_cfg.poll_interval)
        observation = await fetch_openweather_current(ow_cfg)
        if not observation:
            log.warning("[OWM] no data")
            continue
        if is_new_openweather_observation(ow_cfg.key, observation.observed_at_unix):
            message = build_openweather_current_message(observation)
            sent = await send_to_all(bot, message, ow_cfg.chat_ids)
            if sent:
                init_openweather_observation(ow_cfg.key, observation.observed_at_unix)
                log.info("[OWM] new observation: %s", observation.observed_at_utc)
            else:
                log.warning("[OWM] new observation detected but not fully delivered, will retry")
        else:
            log.debug("[OWM] unchanged")


async def run_scanner(bot: Bot, sc: ScannerConfig) -> None:
    await asyncio.gather(
        metar_loop(bot, sc),
        taf_loop(bot, sc),
    )


async def main(scanner_keys: Optional[list] = None) -> None:
    if not cfg.BOT_TOKEN:
        log.error("BOT_TOKEN is not configured")
        return

    keys = scanner_keys or list(cfg.SCANNERS.keys())
    configs = []

    for key in keys:
        if key not in cfg.SCANNERS:
            log.error(f"Scanner '{key}' not found in config.SCANNERS")
            continue
        scanner = cfg.SCANNERS[key]
        configs.append(
            ScannerConfig(
                icao=scanner["icao"],
                chat_ids=scanner["chat_ids"],
                metar_minutes=scanner["metar_minutes"],
            )
        )

    if not configs:
        log.error("No scanner configs available, exiting")
        return

    log.info("=" * 55)
    log.info(f"Start scanners: {[cfg_item.icao for cfg_item in configs]}")
    log.info("  Standard chats: METAR + TAF only")
    log.info("  METAR window: 1 min before to 10 min after expected issue")
    log.info(f"  TAF poll: every {TAF_POLL_INTERVAL // 60} min")
    log.info("=" * 55)

    request = _build_telegram_request(20)
    get_updates_request = _build_telegram_request(4)
    bot = Bot(
        token=cfg.BOT_TOKEN,
        request=request,
        get_updates_request=get_updates_request,
    )
    me = await _authorize_bot(bot)
    if not me:
        return
    log.info(f"  Bot: @{me.username} ({me.full_name})")

    tasks = [run_scanner(bot, sc) for sc in configs]
    if cfg.BLICK.get("chat_ids"):
        tasks.append(blick_loop(bot))
    if _meteofrance_config():
        tasks.append(meteofrance_obs_loop(bot))
    if _icon_configs():
        tasks.append(icon_d2_loop(bot))
    if _wunderground_pws_config():
        tasks.append(wunderground_pws_loop(bot))
    if _openweather_onecall_config():
        tasks.append(openweather_onecall_loop(bot))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped manually")
