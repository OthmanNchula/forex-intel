import asyncio
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.signal import Signal
from app.services.market_data import fetch_ohlcv
from app.services.indicator_engine import compute_all_indicators
from app.services.ai_analysis import generate_ai_signal
from app.services.alert_service import cache_signal

# Pairs and timeframes to scan
SCAN_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "XAU/USD",
    "AUD/USD",
    "USD/CAD",
]

SCAN_TIMEFRAMES = ["H1", "H4"]
SCAN_TIMEFRAMES_OVERLAP = ["M15", "H1", "H4"]

# Minimum thresholds
MIN_CONFIDENCE = 62
MIN_RR_RATIO = 1.5
SCAN_INTERVAL = 3600  # 1 hour default

# Market session windows in UTC — reverted back to narrow ±30-45 min
# windows around each session's actual opening bell, NOT continuous
# 00:00-21:00 coverage. The continuous-coverage version made the engine
# eligible to call the Claude API on almost every scan cycle, all day,
# every trading day — combined with the standalone Railway Cron job
# (which has no memory between runs and re-scans everything on every
# fire), that burned through the Anthropic API credits non-stop. These
# narrow windows mean get_active_session() returns None most of the
# day, so run_signal_scan_cycle() exits immediately without touching
# the AI at all outside these windows — restoring the original
# "~6 hours/day of active scanning" design.
SESSION_RANGES = [
    {"name": "Tokyo Session", "start_hour": 0, "end_hour": 1},
    {"name": "London Session", "start_hour": 7, "end_hour": 8},
    {"name": "New York Open", "start_hour": 12, "end_hour": 13},
    {"name": "London/NY Overlap", "start_hour": 13, "end_hour": 14},
    {"name": "New York Session", "start_hour": 16, "end_hour": 17},
]

# High impact pairs per session
SESSION_PAIRS = {
    "Tokyo Session": ["USD/JPY", "AUD/USD"],
    "London Session": ["EUR/USD", "GBP/USD", "XAU/USD"],
    "New York Open": ["EUR/USD", "GBP/USD", "USD/CAD", "XAU/USD"],
    "London/NY Overlap": ["EUR/USD", "GBP/USD", "XAU/USD", "USD/JPY"],
    "New York Session": ["EUR/USD", "GBP/USD", "USD/CAD", "XAU/USD"],
}


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


def get_active_session(now: datetime) -> Optional[dict]:
    """
    Check which session RANGE the current time falls in (see
    SESSION_RANGES above). Returns session info if active, None otherwise
    (only true outside 00:00–21:00 UTC, i.e. the daily low-liquidity gap).
    """
    hour = now.hour

    for session in SESSION_RANGES:
        if session["start_hour"] <= hour < session["end_hour"]:
            return session

    return None


def get_pairs_for_session(session_name: str) -> list:
    """Get the most relevant pairs for a given session."""
    return SESSION_PAIRS.get(session_name, SCAN_PAIRS)


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


def has_volatility_spike(indicators: dict, pair: str = "") -> bool:
    """
    Check if ATR indicates sufficient volatility for a valid signal.
    Uses pair-specific thresholds instead of a single ratio.
    This fixes the issue where EUR/USD was always failing the check.
    """
    atr = indicators.get("atr", 0)
    if atr == 0:
        return False

    # Get pair-specific threshold
    threshold = PAIR_ATR_THRESHOLDS.get(pair, DEFAULT_ATR_THRESHOLD)

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


def signal_already_exists(db: Session, pair: str, timeframe: str) -> bool:
    """Check if a recent active signal exists for this pair/timeframe."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    existing = db.query(Signal).filter(
        Signal.pair == pair,
        Signal.timeframe == timeframe,
        Signal.is_active == True,
        Signal.direction != "NO_TRADE",
        Signal.created_at >= cutoff,
    ).first()
    return existing is not None


async def analyze_pair(pair: str, timeframe: str) -> Optional[dict]:
    """Analyze a single pair. Only calls Claude AI if pre-checks pass."""
    try:
        # Fetch market data
        df = await fetch_ohlcv(pair, timeframe, 200)
        if df is None:
            return None

        # Compute indicators
        indicators = compute_all_indicators(df)
        if not indicators:
            return None

        # Pre-check directional bias before calling AI
        rsi = indicators.get("rsi", 50)
        ema_cross = indicators.get("ema_cross", "")
        macd_hist = indicators.get("macd_hist", 0)

        bullish_points = sum([
            ema_cross == "ABOVE",
            rsi > 50,
            macd_hist > 0,
        ])
        bearish_points = sum([
            ema_cross == "BELOW",
            rsi < 50,
            macd_hist < 0,
        ])

        # Skip if no clear directional bias — SAVES API CREDITS
        if bullish_points == bearish_points:
            print(f"[AutoSignal] {pair} {timeframe} — mixed signals, skipping AI call")
            return None

        # Skip if no volatility spike during non-session times
        if not has_volatility_spike(indicators, pair):
            print(f"[AutoSignal] {pair} {timeframe} — low volatility, skipping AI call")
            return None

        # Only now call Claude AI
        print(f"[AutoSignal] 🤖 Calling AI for {pair} {timeframe}...")
        ai_result = await generate_ai_signal(pair, timeframe, indicators, df)

        direction = ai_result.get("direction", "NO_TRADE")
        confidence = ai_result.get("confidence_score", 0)
        rr_ratio = ai_result.get("rr_ratio", 0)

        if direction == "NO_TRADE":
            print(f"[AutoSignal] {pair} {timeframe} — AI says NO_TRADE")
            return None

        if confidence < MIN_CONFIDENCE:
            print(f"[AutoSignal] {pair} {timeframe} — confidence {confidence}% below {MIN_CONFIDENCE}%")
            return None

        if rr_ratio and rr_ratio < MIN_RR_RATIO:
            print(f"[AutoSignal] {pair} {timeframe} — R:R {rr_ratio} below {MIN_RR_RATIO}")
            return None

        passes, reason = check_technical_confluence(indicators, direction)
        if not passes:
            print(f"[AutoSignal] {pair} {timeframe} — confluence failed: {reason}")
            return None

        print(f"[AutoSignal] ✅ HIGH PROBABILITY: {pair} {timeframe} {direction} | {confidence}% | R:R {rr_ratio}")
        return {
            "pair": pair,
            "timeframe": timeframe,
            "ai_result": ai_result,
            "indicators": indicators,
        }

    except Exception as e:
        print(f"[AutoSignal] Error analyzing {pair} {timeframe}: {e}")
        return None


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
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
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

        # Send Email notification
        try:
            from app.services.email_service import send_signal_email
            await send_signal_email(ai_result, pair, timeframe)
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
    """Deactivate signals older than 4 hours."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
        expired = db.query(Signal).filter(
            Signal.is_active == True,
            Signal.created_at < cutoff,
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
    Run ONE scan cycle and return immediately — no loop, no sleep.

    This is the reusable core used by both:
    - the in-process background loop (auto_signal_loop), which only runs
      while the web dyno happens to be awake, and
    - the standalone Railway Cron entrypoint (backend/cron_scan.py), which
      runs on its own schedule regardless of whether the web process is
      idle. The cron path is what guarantees scans actually happen —
      the in-process loop is just a bonus when the dyno is already up.

    Safe to call repeatedly within the same session window: session
    detection (30-min window) plus the 4-hour dedup in
    signal_already_exists() prevent duplicate signals if this fires
    more than once while a session is still "active".
    """
    now = datetime.now(timezone.utc)

    if not is_market_open():
        print(f"[AutoSignal] 😴 Market closed at {now.strftime('%H:%M UTC')}")
        return {"scanned": False, "reason": "market_closed"}

    active_session = get_active_session(now)
    if active_session is None:
        print(f"[AutoSignal] ⏰ No session open at {now.strftime('%H:%M UTC')}")
        return {"scanned": False, "reason": "no_session"}

    session_name = active_session["name"]
    print(f"\n[AutoSignal] 🔔 {session_name} detected at {now.strftime('%H:%M UTC')}")

    await expire_old_signals()

    pairs_to_scan = get_pairs_for_session(session_name)
    print(f"[AutoSignal] Scanning {len(pairs_to_scan)} pairs: {', '.join(pairs_to_scan)}")

    signals_generated = 0

    # Use M15 during highest liquidity sessions for more opportunities
    if session_name in ["London/NY Overlap", "New York Open"]:
        timeframes_to_scan = ["M15", "H1", "H4"]
        print(f"[AutoSignal] Using M15+H1+H4 (high liquidity session)")
    else:
        timeframes_to_scan = SCAN_TIMEFRAMES

    for pair in pairs_to_scan:
        for timeframe in timeframes_to_scan:
            await asyncio.sleep(2)
            result = await analyze_pair(pair, timeframe)
            if result:
                saved = await save_auto_signal(result)
                if saved:
                    signals_generated += 1

    print(f"[AutoSignal] ✅ {session_name} scan complete — {signals_generated} signals generated")
    return {
        "scanned": True,
        "session": session_name,
        "pairs": pairs_to_scan,
        "signals_generated": signals_generated,
    }


async def auto_signal_loop():
    """
    In-process background loop — a bonus scan path that only runs while
    the web dyno is awake. Checks every 30 minutes and delegates the
    actual work to run_signal_scan_cycle(). The Railway Cron job
    (backend/cron_scan.py) is the reliable path; this loop just adds
    extra coverage for free when the process happens to be up anyway.
    """
    print("[AutoSignal] 🚀 In-process Auto Signal loop started (bonus coverage)")
    print("[AutoSignal] Strategy: Session-based scanning + volatility filter")
    print(f"[AutoSignal] Sessions: Tokyo(00:00) London(07:00) NewYork(12:00) UTC")
    print(f"[AutoSignal] Min confidence: {MIN_CONFIDENCE}% | Min R:R: {MIN_RR_RATIO}")

    await asyncio.sleep(30)

    last_session_scanned = None

    while True:
        try:
            now = datetime.now(timezone.utc)
            active_session = get_active_session(now)
            session_name = active_session["name"] if active_session else None

            if session_name and session_name != last_session_scanned:
                result = await run_signal_scan_cycle()
                if result.get("scanned"):
                    last_session_scanned = session_name
            else:
                print(f"[AutoSignal] ⏭ Nothing new at {now.strftime('%H:%M UTC')} — checking in 30 mins")

        except Exception as e:
            print(f"[AutoSignal] Loop error: {e}")

        await asyncio.sleep(1800)  # check every 30 minutes