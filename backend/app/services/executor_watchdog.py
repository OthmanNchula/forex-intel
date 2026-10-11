"""
Executor watchdog — tells you when the VPS executor stops running.

The executor polls /api/analysis/signals/executable every 30 seconds, so
every poll doubles as a heartbeat. If no poll arrives for
EXECUTOR_OFFLINE_MINUTES (default 10), one alert goes out by email (to
EXECUTOR_ALERT_EMAIL, else JOURNAL_OWNER_EMAIL, else NOTIFICATION_EMAIL)
and Telegram. When polls resume, one "back online" message follows.

The last-seen time lives in memory and is copied to Redis at most every
few minutes, so a Railway redeploy does not forget an executor that was
already offline.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services.alert_service import redis

OFFLINE_AFTER = timedelta(minutes=float(os.getenv("EXECUTOR_OFFLINE_MINUTES", "10")))
REDIS_KEY = "executor:last_poll"
REDIS_WRITE_EVERY = timedelta(minutes=3)

_last_poll: Optional[datetime] = None
_last_redis_write: Optional[datetime] = None
_alerted = False
_booted_at = datetime.now(timezone.utc)
_loaded_from_redis = False


def record_executor_poll() -> None:
    """Called on every executor poll."""
    global _last_poll, _last_redis_write
    now = datetime.now(timezone.utc)
    _last_poll = now
    if redis is not None and (_last_redis_write is None or now - _last_redis_write > REDIS_WRITE_EVERY):
        try:
            redis.set(REDIS_KEY, now.isoformat())
            _last_redis_write = now
        except Exception as e:
            print(f"[Watchdog] could not save heartbeat to Redis: {e}")


def _load_from_redis_once() -> None:
    global _last_poll, _loaded_from_redis
    if _loaded_from_redis:
        return
    _loaded_from_redis = True
    if _last_poll is None and redis is not None:
        try:
            raw = redis.get(REDIS_KEY)
            if raw:
                _last_poll = datetime.fromisoformat(raw)
        except Exception as e:
            print(f"[Watchdog] could not read heartbeat from Redis: {e}")


def _recipient() -> str:
    for var in ("EXECUTOR_ALERT_EMAIL", "JOURNAL_OWNER_EMAIL", "NOTIFICATION_EMAIL"):
        val = os.getenv(var, "").split(",")[0].strip()
        if val:
            return val
    return ""


async def _notify(subject: str, text: str) -> None:
    try:
        from app.services.telegram_service import send_telegram_message
        await send_telegram_message(f"<b>{subject}</b>\n{text}")
    except Exception as e:
        print(f"[Watchdog] Telegram failed: {e}")
    to = _recipient()
    if to:
        try:
            from app.services.email_service import send_to_address
            html = f"<h3>{subject}</h3><p>{text.replace(chr(10), '<br>')}</p>"
            await send_to_address(to, f"Forex Intel — {subject}", html)
        except Exception as e:
            print(f"[Watchdog] email failed: {e}")


async def check_executor_alive() -> None:
    """Called once a minute from the scanner loop."""
    global _alerted
    _load_from_redis_once()
    now = datetime.now(timezone.utc)
    reference = _last_poll or _booted_at
    silent_for = now - reference

    if silent_for > OFFLINE_AFTER and not _alerted:
        _alerted = True
        last_txt = (_last_poll.strftime("%Y-%m-%d %H:%M UTC") if _last_poll
                    else "not since the server restarted")
        print(f"[Watchdog] ⚠️ executor silent for {int(silent_for.total_seconds() // 60)} min — alerting")
        await _notify(
            "⚠️ Trading executor is OFFLINE",
            f"The MT5 executor on the VPS has not checked in for "
            f"{int(silent_for.total_seconds() // 60)} minutes (last seen: {last_txt}).\n"
            f"No trades will be placed or journaled until it is running again.\n"
            f"Likely causes: VPS restarted (e.g. Windows Update), executor window closed, "
            f"MT5 logged out, or the VPS lost internet.",
        )
    elif silent_for <= OFFLINE_AFTER and _alerted:
        _alerted = False
        print("[Watchdog] ✅ executor back online")
        await _notify("✅ Trading executor is back online",
                      f"The executor checked in again at {now.strftime('%Y-%m-%d %H:%M UTC')}.")
