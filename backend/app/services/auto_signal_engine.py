import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.signal import Signal
from app.services.market_data import fetch_ohlcv
from app.services.indicator_engine import compute_all_indicators
from app.services import rules_engine
from app.services.alert_service import (
    cache_signal,
    is_within_ai_call_budget,
    increment_monthly_ai_call_count,
    is_within_daily_ai_call_budget,
    increment_daily_ai_call_count,
    redis_heartbeat,
    claim_scan_candle,
    release_scan_candle,
)

# Pairs and timeframes to scan
SCAN_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "XAU/USD",
    "AUD/USD",
    "USD/CAD",
]
# Optional override from the environment, e.g. SCAN_PAIRS="USD/CAD,GBP/USD"
_env_pairs = os.getenv("SCAN_PAIRS", "").strip()
if _env_pairs:
    SCAN_PAIRS = [p.strip().upper() for p in _env_pairs.split(",") if p.strip()]

SCAN_TIMEFRAMES = ["H1", "H4"]
SCAN_TIMEFRAMES_OVERLAP = ["M15", "H1", "H4"]

# Minimum thresholds
MIN_CONFIDENCE = 62
MIN_RR_RATIO = 1.5
SCAN_INTERVAL = 3600  # 1 hour default

# How long a signal stays "active" before it's swept away by
# expire_old_signals(), scaled to the timeframe it was generated from.
# A flat expiry (e.g. always 4 hours) doesn't make sense across
# timeframes: an H4 setup is built on a candle that itself takes 4
# hours to close, so it should stay valid for a good while past that;
# an M15 scalp setup goes stale much sooner than 4 hours. Each value
# here is roughly "a handful of candles" for that timeframe — long
# enough for the setup to still be relevant, short enough that it
# doesn't linger once price has clearly moved on.
SIGNAL_EXPIRY_HOURS = {
    "M15": 1.5,   # ~6 candles
    "H1": 5,      # ~5 candles
    "H4": 18,     # ~4-5 candles
    "D1": 60,     # ~2.5 days
}
DEFAULT_SIGNAL_EXPIRY_HOURS = 4  # fallback for any timeframe not listed above


# A signal is only actionable right after its candle closes: once price has
# moved on, the entry zone is stale. So every signal (any timeframe, auto or
# manual) is active for SIGNAL_ACTIVE_MINUTES only, then expires.
# Set SIGNAL_ACTIVE_MINUTES=0 in Railway to go back to the per-timeframe
# hours above.
SIGNAL_ACTIVE_MINUTES = float(os.getenv("SIGNAL_ACTIVE_MINUTES", "5"))


def get_signal_expiry_hours(timeframe: str) -> float:
    """How many hours a signal generated on this timeframe should stay active."""
    if SIGNAL_ACTIVE_MINUTES > 0:
        return SIGNAL_ACTIVE_MINUTES / 60.0
    return SIGNAL_EXPIRY_HOURS.get(timeframe, DEFAULT_SIGNAL_EXPIRY_HOURS)

# There is deliberately NO per-pair/timeframe cooldown here anymore (it
# was removed at the user's request) — every pair/timeframe that clears
# the free pre-checks below gets analyzed by the AI every time it's
# scanned, with no "already checked recently" skip. That means cost
# control rests ENTIRELY on the hard monthly cap right below, not on
# reducing how often the AI gets called. A volatile session scanned
# often (e.g. by the 15-min standalone cron) can burn through the
# monthly budget faster than it would with a cooldown — see the note
# inside analyze_pair() for the full trade-off.

# Hard monthly cap on AI calls — this is what actually guarantees a
# dollar ceiling, unlike the cooldown/session-window tuning above which
# only reduce the AVERAGE case. Based on this account's real observed
# cost of ~$0.02/call (Sonnet, ~2,200 input + ~900 output tokens per
# call): 900 calls/month x $0.02 ≈ $18, leaving headroom under a $20/mo
# target even if the per-call cost drifts a bit. Once this is hit,
# analyze_pair() stops calling the AI for the rest of the calendar month
# and falls back to a technical-indicators-only signal instead of going
# silent — see generate_technical_fallback_signal() below.
MONTHLY_AI_CALL_BUDGET = int(os.getenv("MONTHLY_AI_CALL_BUDGET", "900"))

# Daily slice of the monthly budget — spreads MONTHLY_AI_CALL_BUDGET
# evenly across a 30-day month so a single volatile day (or week) can't
# spend the whole month's calls at once and leave nothing but
# technical-only fallback signals for the rest of the month. Once
# today's slice is used up, the engine falls back to technical-only for
# the REST OF TODAY specifically and picks the AI back up tomorrow, even
# if the overall monthly budget still has room left — "wait for
# tomorrow," not "wait for next month."
DAILY_AI_CALL_BUDGET = MONTHLY_AI_CALL_BUDGET // 30  # = 30 calls/day

# Continuous scanning: the engine no longer sleeps between "session
# windows" or checks every 30 minutes. It wakes every minute while the
# market is open (Sunday 22:00 UTC to Friday 22:00 UTC, see
# is_market_open()) and analyzes a pair/timeframe the moment a NEW candle
# has closed on it — once per candle, using closed candles only. That
# keeps the entry as close to the candle close as possible, and it also
# bounds AI spend: H1 is analyzed at most once an hour per pair, H4 once
# every four hours, M15 once every 15 minutes.
TIMEFRAME_MINUTES = {"M15": 15, "H1": 60, "H4": 240}

# Wait this long after a candle closes before analyzing it, so the data
# provider has time to publish the finished candle.
CANDLE_CLOSE_DELAY_SECONDS = 45

# If a candle closed more than this long ago and was never analyzed (the
# service was down, say), skip it rather than send a stale signal.
CANDLE_GRACE_MINUTES = 10

# M15 is only scanned in the highest-liquidity hours (London/NY overlap
# and NY open) — it is the most expensive timeframe to scan continuously.
M15_SCAN_HOURS_UTC = range(12, 17)

# M15 scanning is OFF by default: the backtest has not shown it is worth
# trading and its first live trades lost. Set SCAN_M15=true to switch it on.
SCAN_M15 = os.getenv("SCAN_M15", "false").strip().lower() == "true"

# How often the in-process loop wakes up to look for newly closed candles.
LOOP_CHECK_SECONDS = 60


def latest_candle_boundary(now: datetime, timeframe: str) -> datetime:
    """Start time (UTC) of the most recent candle boundary for this timeframe."""
    minutes = TIMEFRAME_MINUTES[timeframe]
    epoch_minutes = int(now.timestamp() // 60)
    return datetime.fromtimestamp((epoch_minutes // minutes) * minutes * 60, tz=timezone.utc)


def timeframes_for_now(now: datetime) -> list:
    """Timeframes worth scanning right now."""
    if SCAN_M15 and now.hour in M15_SCAN_HOURS_UTC:
        return ["M15", "H1", "H4"]
    return ["H1", "H4"]


def drop_forming_candle(df, timeframe: str):
    """Remove the still-open last candle so indicators use closed candles only."""
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None or df is None or len(df) < 2:
        return df
    last_open = df.index[-1]
    if last_open.tzinfo is None:
        last_open = last_open.tz_localize("UTC")
    if last_open + timedelta(minutes=minutes) > datetime.now(timezone.utc):
        return df.iloc[:-1]
    return df


def is_market_open() -> bool:
    """Check if Forex market is active."""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    hour = now.hour

    # Skip Saturday
    if weekday == 5:
        return False
    # Skip Sunday before 22:00
    if weekday == 6 and hour < 22:
        return False
    # Skip Friday after 22:00
    if weekday == 4 and hour >= 22:
        return False

    return True


# Pair-specific minimum ATR values
# Based on each pair's typical daily movement
PAIR_ATR_THRESHOLDS = {
    "EUR/USD": 0.00035,   # typical H1 ATR for EURUSD
    "GBP/USD": 0.00045,   # GBP moves more than EUR
    "USD/JPY": 0.035,     # JPY pairs have different pip size
    "USD/CHF": 0.00035,   # similar to EURUSD
    "AUD/USD": 0.00035,   # similar to EURUSD
    "USD/CAD": 0.00040,   # slightly higher
    "XAU/USD": 0.40,      # Gold moves in dollars not pips
}

DEFAULT_ATR_THRESHOLD = 0.00035  # fallback for unknown pairs


# The thresholds above are calibrated for H1. Smaller candles move less,
# so M15 uses half of them.
TIMEFRAME_ATR_SCALE = {"M15": 0.5, "H1": 1.0, "H4": 1.0}


def has_volatility_spike(indicators: dict, pair: str = "", timeframe: str = "H1") -> bool:
    """
    Check if ATR indicates sufficient volatility for a valid signal.
    Uses pair-specific thresholds instead of a single ratio.
    This fixes the issue where EUR/USD was always failing the check.
    """
    atr = indicators.get("atr", 0)
    if atr == 0:
        return False

    # Get pair-specific threshold
    threshold = PAIR_ATR_THRESHOLDS.get(pair, DEFAULT_ATR_THRESHOLD) * TIMEFRAME_ATR_SCALE.get(timeframe, 1.0)

    passes = atr >= threshold
    if not passes:
        print(f"[AutoSignal] ATR {atr:.5f} below threshold {threshold:.5f} for {pair}")
    return passes


def check_technical_confluence(indicators: dict, direction: str) -> tuple[bool, str]:
    """Check if all technical indicators confirm the trade direction."""
    rsi = indicators.get("rsi", 50)
    macd_hist = indicators.get("macd_hist", 0)
    ema_cross = indicators.get("ema_cross", "BELOW")
    ema20_slope = indicators.get("ema20_slope", 0)
    trend = indicators.get("trend", "NEUTRAL")

    if direction == "BUY":
        if ema_cross != "ABOVE":
            return False, "EMA20 below EMA50 — no bullish trend"
        if rsi < 35 or rsi > 68:
            return False, f"RSI {rsi:.1f} not in buy zone (35-68)"
        if macd_hist < 0:
            return False, f"MACD histogram bearish"
        if ema20_slope < 0:
            return False, "EMA20 slope falling"
        if trend == "BEARISH":
            return False, "Overall trend bearish"
        return True, "All BUY conditions confirmed"

    elif direction == "SELL":
        if ema_cross != "BELOW":
            return False, "EMA20 above EMA50 — no bearish trend"
        if rsi > 65 or rsi < 32:
            return False, f"RSI {rsi:.1f} not in sell zone (32-65)"
        if macd_hist > 0:
            return False, "MACD histogram bullish"
        if ema20_slope > 0:
            return False, "EMA20 slope rising"
        if trend == "BULLISH":
            return False, "Overall trend bullish"
        return True, "All SELL conditions confirmed"

    return False, "Direction is NO_TRADE"


# Fixed risk-reward multiples (in ATR) used ONLY when the monthly AI
# budget is exhausted and we fall back to a technical-only signal. These
# are a standard ATR-based stop/target approach, not something the AI
# would necessarily choose — no support/resistance awareness, no
# candlestick pattern read, no written reasoning. Treat these signals as
# strictly lower-confidence than an AI-confirmed one.
TECHNICAL_FALLBACK_SL_ATR_MULTIPLE = 1.5
TECHNICAL_FALLBACK_TP1_ATR_MULTIPLE = 2.25   # RR 1.5
TECHNICAL_FALLBACK_TP2_ATR_MULTIPLE = 3.0    # RR 2.0
TECHNICAL_FALLBACK_TP3_ATR_MULTIPLE = 3.75   # RR 2.5
TECHNICAL_FALLBACK_CONFIDENCE = 55           # deliberately below MIN_CONFIDENCE (62)


def generate_technical_fallback_signal(pair: str, timeframe: str, indicators: dict, direction: str) -> dict:
    """
    Build a signal from indicators alone, with no AI call — used only
    when MONTHLY_AI_CALL_BUDGET has been reached for the month. Entry/
    stop/targets come from fixed ATR multiples rather than an AI reading
    of support/resistance or price action, so this is intentionally a
    lower-confidence, lower-information signal than a normal AI one —
    it exists so the account doesn't go completely silent for the rest
    of the month, not as a like-for-like replacement.

    The fallback nature is recorded directly in ai_explanation (rather
    than a new DB column, which would need a migration) so it's visible
    wherever ai_explanation is already displayed — the app UI, the
    Telegram/email notifications — without any other code needing to
    change to know the difference.
    """
    price = indicators["current_price"]
    atr = indicators.get("atr", 0)
    rsi = indicators.get("rsi", 50)
    macd_hist = indicators.get("macd_hist", 0)

    if direction == "BUY":
        entry_low = round(price - atr * 0.1, 5)
        entry_high = round(price + atr * 0.1, 5)
        stop_loss = round(price - atr * TECHNICAL_FALLBACK_SL_ATR_MULTIPLE, 5)
        tp1 = round(price + atr * TECHNICAL_FALLBACK_TP1_ATR_MULTIPLE, 5)
        tp2 = round(price + atr * TECHNICAL_FALLBACK_TP2_ATR_MULTIPLE, 5)
        tp3 = round(price + atr * TECHNICAL_FALLBACK_TP3_ATR_MULTIPLE, 5)
    else:  # SELL
        entry_low = round(price - atr * 0.1, 5)
        entry_high = round(price + atr * 0.1, 5)
        stop_loss = round(price + atr * TECHNICAL_FALLBACK_SL_ATR_MULTIPLE, 5)
        tp1 = round(price - atr * TECHNICAL_FALLBACK_TP1_ATR_MULTIPLE, 5)
        tp2 = round(price - atr * TECHNICAL_FALLBACK_TP2_ATR_MULTIPLE, 5)
        tp3 = round(price - atr * TECHNICAL_FALLBACK_TP3_ATR_MULTIPLE, 5)

    return {
        "direction": direction,
        "current_price": price,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "rr_ratio": TECHNICAL_FALLBACK_TP1_ATR_MULTIPLE / TECHNICAL_FALLBACK_SL_ATR_MULTIPLE,
        "confidence_score": TECHNICAL_FALLBACK_CONFIDENCE,
        "ai_explanation": (
            "[TECHNICAL-ONLY — monthly AI budget reached] This signal was generated from "
            f"indicator confluence only (EMA20/50 cross, RSI {rsi:.1f}, MACD histogram "
            f"{macd_hist:.5f}) with fixed ATR-based risk levels — no AI review of price "
            "action, support/resistance, or written reasoning. Treat with more caution "
            "than a normal AI-confirmed signal."
        ),
        "risk_warning": (
            "Generated without AI confirmation because this month's AI analysis budget "
            "has been used up. Entry/stop/target levels are simple ATR multiples, not a "
            "reasoned read of the chart. Trading Forex involves significant risk of loss."
        ),
        "ema20": indicators.get("ema20"),
        "ema50": indicators.get("ema50"),
        "rsi": rsi,
        "macd_hist": macd_hist,
        "atr": atr,
    }


def signal_already_exists(db: Session, pair: str, timeframe: str) -> bool:
    """
    Check if an active signal already exists for this pair/timeframe.

    Relies solely on is_active — which expire_old_signals() keeps
    accurate per-signal using each signal's own expires_at (see
    get_signal_expiry_hours: 1.5h for M15, 5h for H1, 18h for H4, 60h
    for D1) — rather than a second, independent time window here.

    This used to also require created_at within a flat 4-hour cutoff,
    which was fine for M15/H1 (their real expiry is under 4h anyway)
    but actively wrong for H4 (18h) and D1 (60h): once more than 4
    hours had passed since an H4/D1 signal was created, this check
    would stop finding it — even though it was still genuinely active
    — and let a duplicate signal be saved for the same pair/timeframe
    on top of one that hadn't expired yet.
    """
    existing = db.query(Signal).filter(
        Signal.pair == pair,
        Signal.timeframe == timeframe,
        Signal.is_active == True,
        Signal.direction != "NO_TRADE",
    ).first()
    return existing is not None


# Twelve Data's free plan allows about 8 requests a minute (and the live
# price feed shares the same key), so scanner requests are spaced out.
# A request that still fails (e.g. 429) returns None -> the pair/timeframe
# is retried on the next pass instead of being lost.
MIN_SECONDS_BETWEEN_FETCHES = 9
_fetch_lock = asyncio.Lock()
_last_fetch_at = 0.0


async def _throttled_fetch(pair: str, timeframe: str, limit: int):
    global _last_fetch_at
    async with _fetch_lock:
        wait = MIN_SECONDS_BETWEEN_FETCHES - (asyncio.get_event_loop().time() - _last_fetch_at)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await fetch_ohlcv(pair, timeframe, limit)
        finally:
            _last_fetch_at = asyncio.get_event_loop().time()


# Returned by analyze_pair when market data could not be fetched, so the
# scan pass can release the candle and try again shortly.
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"

# Each timeframe is checked against the next one up.
HIGHER_TIMEFRAME = {"M15": "H1", "H1": "H4"}
_HTF_CACHE: dict = {}          # (pair, tf) -> (fetched_at, ema_cross)
HTF_CACHE_MINUTES = 20


async def get_higher_timeframe_cross(pair: str, timeframe: str) -> Optional[str]:
    """EMA20-vs-EMA50 state ("ABOVE"/"BELOW") of the next timeframe up, or None."""
    htf = HIGHER_TIMEFRAME.get(timeframe)
    if htf is None:
        return None
    key = (pair, htf)
    cached = _HTF_CACHE.get(key)
    now = datetime.now(timezone.utc)
    if cached and now - cached[0] < timedelta(minutes=HTF_CACHE_MINUTES):
        return cached[1]
    try:
        df = await _throttled_fetch(pair, htf, 120)
        df = drop_forming_candle(df, htf)
        ind = compute_all_indicators(df, include_chart=False) if df is not None else None
        cross = ind.get("ema_cross") if ind else None
    except Exception as e:
        print(f"[AutoSignal] {pair} {htf} higher-timeframe check failed: {e}")
        cross = None
    if cross is not None:      # never cache a failed lookup
        _HTF_CACHE[key] = (now, cross)
    return cross


async def analyze_pair(pair: str, timeframe: str) -> Optional[dict]:
    """
    Analyze one pair/timeframe on its latest CLOSED candle using the
    rules engine (see rules_engine.py). No AI is called anywhere here, so
    this costs nothing per scan. Returns a signal dict, or None when the
    engine decides to stand aside (the reason is always logged).
    """
    try:
        df = await _throttled_fetch(pair, timeframe, 200)
        if df is None:
            print(f"[AutoSignal] {pair} {timeframe} — no market data, will retry shortly")
            return DATA_UNAVAILABLE
        df = drop_forming_candle(df, timeframe)
        candle_tag = f"candle {df.index[-1]:%d %H:%M}" if len(df) else "no candles"

        indicators = compute_all_indicators(df, include_chart=False)
        if not indicators:
            print(f"[AutoSignal] {pair} {timeframe} — not enough candles, will retry shortly")
            return DATA_UNAVAILABLE

        if not has_volatility_spike(indicators, pair, timeframe):
            print(f"[AutoSignal] {pair} {timeframe} ({candle_tag}) — stand aside: market too quiet")
            return None

        htf_cross = await get_higher_timeframe_cross(pair, timeframe)
        decision = rules_engine.evaluate(pair, timeframe, indicators, htf_cross)

        if decision["action"] != "TRADE":
            print(f"[AutoSignal] {pair} {timeframe} ({candle_tag}) — stand aside "
                  f"[{decision['regime']}]: {decision['reason']}")
            return None

        signal = decision["signal"]
        print(f"[AutoSignal] ✅ RULES SIGNAL: {pair} {timeframe} ({candle_tag}) {signal['direction']} | "
              f"score {decision['score']} | regime {decision['regime']} | R:R {signal['rr_ratio']}")
        return {
            "pair": pair,
            "timeframe": timeframe,
            "ai_result": signal,
            "indicators": indicators,
        }

    except Exception as e:
        print(f"[AutoSignal] Error analyzing {pair} {timeframe}: {e}")
        return DATA_UNAVAILABLE


async def save_auto_signal(signal_data: dict) -> Optional[Signal]:
    """Save a confirmed auto signal to the database."""
    db = SessionLocal()
    try:
        pair = signal_data["pair"]
        timeframe = signal_data["timeframe"]
        ai_result = signal_data["ai_result"]

        if signal_already_exists(db, pair, timeframe):
            print(f"[AutoSignal] Signal already exists for {pair} {timeframe}")
            return None

        from datetime import timedelta
        signal = Signal(
            pair=pair,
            timeframe=timeframe,
            direction=ai_result["direction"],
            current_price=ai_result["current_price"],
            entry_low=ai_result.get("entry_low"),
            entry_high=ai_result.get("entry_high"),
            stop_loss=ai_result.get("stop_loss"),
            take_profit_1=ai_result.get("take_profit_1"),
            take_profit_2=ai_result.get("take_profit_2"),
            take_profit_3=ai_result.get("take_profit_3"),
            rr_ratio=ai_result.get("rr_ratio"),
            confidence_score=ai_result.get("confidence_score"),
            ai_explanation=ai_result.get("ai_explanation"),
            risk_warning=ai_result.get("risk_warning"),
            ema20=ai_result.get("ema20"),
            ema50=ai_result.get("ema50"),
            rsi=ai_result.get("rsi"),
            macd_hist=ai_result.get("macd_hist"),
            atr=ai_result.get("atr"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=get_signal_expiry_hours(timeframe)),
            is_active=True,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        signal_dict = {
            "id": str(signal.id),
            "pair": signal.pair,
            "timeframe": signal.timeframe,
            "direction": signal.direction,
            "current_price": signal.current_price,
            "entry_low": signal.entry_low,
            "entry_high": signal.entry_high,
            "stop_loss": signal.stop_loss,
            "take_profit_1": signal.take_profit_1,
            "take_profit_2": signal.take_profit_2,
            "take_profit_3": signal.take_profit_3,
            "rr_ratio": signal.rr_ratio,
            "confidence_score": signal.confidence_score,
            "ai_explanation": signal.ai_explanation,
            "risk_warning": signal.risk_warning,
            "ema20": signal.ema20,
            "ema50": signal.ema50,
            "rsi": signal.rsi,
            "macd_hist": signal.macd_hist,
            "atr": signal.atr,
            "is_active": signal.is_active,
            "created_at": signal.created_at.isoformat(),
        }
        cache_signal(pair, timeframe, signal_dict)

        print(f"[AutoSignal] 💾 Saved: {pair} {timeframe} {signal.direction} @ {signal.current_price}")
        
        # Send Telegram notification
        try:
            from app.services.telegram_service import send_signal_notification
            await send_signal_notification(ai_result, pair, timeframe)
        except Exception as e:
            print(f"[AutoSignal] Telegram notification failed: {e}")

        # Send Email notification — to every registered user watching
        # this pair (see get_signal_recipient_emails in email_service.py),
        # using this same db session since it's already open here.
        try:
            from app.services.email_service import send_signal_email
            await send_signal_email(ai_result, pair, timeframe, db)
        except Exception as e:
            print(f"[AutoSignal] Email notification failed: {e}")

        return signal

    except Exception as e:
        print(f"[AutoSignal] Error saving: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def expire_old_signals():
    """
    Deactivate signals whose per-timeframe expires_at has passed.

    Uses each signal's own expires_at (set at creation from
    get_signal_expiry_hours(), based on the timeframe it was generated
    on) rather than a single flat cutoff — an H4 signal and an M15
    signal created at the same moment expire at different times.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = db.query(Signal).filter(
            Signal.is_active == True,
            Signal.expires_at.isnot(None),
            Signal.expires_at < now,
        ).all()
        for signal in expired:
            signal.is_active = False
        db.commit()
        if expired:
            print(f"[AutoSignal] Expired {len(expired)} old signals")
    except Exception as e:
        print(f"[AutoSignal] Error expiring: {e}")
    finally:
        db.close()


async def run_signal_scan_cycle() -> dict:
    """
    Run ONE scan pass and return immediately — no loop, no sleep between
    passes. Safe to call as often as every minute.

    Whenever the market is open, every pair is checked on every enabled
    timeframe, but a pair/timeframe is only ANALYZED when a new candle
    has just closed on it and nobody has claimed that candle yet (see
    claim_scan_candle). Most passes therefore do nothing but a few clock
    comparisons and one Redis lookup per pair/timeframe — no market-data
    or AI calls.

    Used by both the in-process loop (auto_signal_loop, every minute)
    and the standalone Railway Cron entrypoint (backend/cron_scan.py),
    which acts as a backup. They can overlap safely: the Redis claim
    guarantees a candle is analyzed once.
    """
    now = datetime.now(timezone.utc)

    # Keep Redis from ever going idle long enough to be auto-deleted.
    redis_heartbeat()

    # Expire first, every minute, even when the market is closed — otherwise
    # Friday's last signals would stay "active" all weekend.
    await expire_old_signals()

    if not is_market_open():
        return {"scanned": False, "reason": "market_closed"}

    due = []
    for timeframe in timeframes_for_now(now):
        boundary = latest_candle_boundary(now, timeframe)
        age = now - boundary
        if age < timedelta(seconds=CANDLE_CLOSE_DELAY_SECONDS):
            continue  # candle only just closed — give the data provider a moment
        if age > timedelta(minutes=CANDLE_GRACE_MINUTES):
            continue  # too old to be worth a signal
        for pair in SCAN_PAIRS:
            if claim_scan_candle(pair, timeframe, int(boundary.timestamp())):
                due.append((pair, timeframe, boundary))

    if not due:
        return {"scanned": False, "reason": "no_new_candles"}

    print(f"\n[AutoSignal] 🔔 {now.strftime('%H:%M UTC')} — "
          f"{len(due)} newly closed candle(s) to analyze: "
          + ", ".join(f"{p} {tf}" for p, tf, _ in due))

    signals_generated = 0
    retry_later = 0
    for pair, timeframe, boundary in due:
        result = await analyze_pair(pair, timeframe)
        if result == DATA_UNAVAILABLE:
            release_scan_candle(pair, timeframe, int(boundary.timestamp()))
            retry_later += 1
            continue
        if result:
            saved = await save_auto_signal(result)
            if saved:
                signals_generated += 1

    print(f"[AutoSignal] ✅ scan complete — {signals_generated} signals generated"
          + (f", {retry_later} to retry (data unavailable)" if retry_later else ""))
    return {
        "scanned": True,
        "analyzed": [f"{p} {tf}" for p, tf, _ in due],
        "signals_generated": signals_generated,
    }


async def auto_signal_loop():
    """
    In-process background loop. Wakes up every LOOP_CHECK_SECONDS (60s)
    for as long as the web service is running and delegates to
    run_signal_scan_cycle(), which only does real work when a candle has
    just closed. There is no session window and no 30-minute gap: the
    engine covers the whole market-open period, Sunday 22:00 UTC to
    Friday 22:00 UTC.
    """
    print("[AutoSignal] 🚀 Continuous scanner started — analyzes each pair the "
          "moment a candle closes, whenever the market is open")
    print(f"[AutoSignal] Pairs: {', '.join(SCAN_PAIRS)} | "
          f"Min confidence: {MIN_CONFIDENCE}% | Min R:R: {MIN_RR_RATIO}")

    await asyncio.sleep(30)

    while True:
        try:
            await run_signal_scan_cycle()
        except Exception as e:
            print(f"[AutoSignal] Loop error: {e}")

        await asyncio.sleep(LOOP_CHECK_SECONDS)
