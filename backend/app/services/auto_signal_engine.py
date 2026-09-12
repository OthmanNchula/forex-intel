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

# Key market session opens in UTC
# These are the highest liquidity moments — best for signals
SESSION_OPENS = [
    {"name": "Tokyo Open", "hour": 0, "minute": 0},
    {"name": "London Open", "hour": 7, "minute": 0},
    {"name": "New York Open", "hour": 12, "minute": 0},
    {"name": "London/NY Overlap", "hour": 13, "minute": 0},
    {"name": "London Close", "hour": 16, "minute": 0},
    {"name": "NY Close", "hour": 21, "minute": 0},
]

# High impact pairs per session
SESSION_PAIRS = {
    "Tokyo Open": ["USD/JPY", "AUD/USD"],
    "London Open": ["EUR/USD", "GBP/USD", "XAU/USD"],
    "New York Open": ["EUR/USD", "GBP/USD", "USD/CAD", "XAU/USD"],
    "London/NY Overlap": ["EUR/USD", "GBP/USD", "XAU/USD", "USD/JPY"],
    "London Close": ["EUR/USD", "GBP/USD"],
    "NY Close": ["XAU/USD", "USD/JPY"],
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
    Check if current time is within 30 minutes of a session open.
    Returns session info if active, None otherwise.
    This is the smart trigger — only scan near session opens.
    """
    hour = now.hour
    minute = now.minute

    for session in SESSION_OPENS:
        session_hour = session["hour"]
        session_minute = session["minute"]

        # Calculate minutes difference
        current_total = hour * 60 + minute
        session_total = session_hour * 60 + session_minute

        diff = abs(current_total - session_total)

        # Trigger within 30 minutes of session open
        if diff <= 30:
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


async def auto_signal_loop():
    """
    Smart background loop:
    - Checks every 30 minutes if we're near a session open
    - Only scans relevant pairs for that session
    - Only calls Claude AI if indicators show clear directional bias
    - Skips low volatility markets
    This reduces API calls by ~90% vs scanning everything every 15 mins
    """
    print("[AutoSignal] 🚀 Smart Auto Signal Engine started")
    print("[AutoSignal] Strategy: Session-based scanning + volatility filter")
    print(f"[AutoSignal] Sessions: Tokyo(00:00) London(07:00) NewYork(12:00) UTC")
    print(f"[AutoSignal] Min confidence: {MIN_CONFIDENCE}% | Min R:R: {MIN_RR_RATIO}")

    await asyncio.sleep(30)

    last_session_scanned = None

    while True:
        try:
            now = datetime.now(timezone.utc)

            # Check if market is open
            if not is_market_open():
                print(f"[AutoSignal] 😴 Market closed at {now.strftime('%H:%M UTC')} — checking again in 30 mins")
                await asyncio.sleep(1800)
                continue

            # Check if we're near a session open
            active_session = get_active_session(now)

            if active_session is None:
                print(f"[AutoSignal] ⏰ No session open at {now.strftime('%H:%M UTC')} — checking in 30 mins")
                await asyncio.sleep(1800)
                continue

            session_name = active_session["name"]

            # Don't scan the same session twice
            if session_name == last_session_scanned:
                print(f"[AutoSignal] ⏭ Already scanned {session_name} — checking in 30 mins")
                await asyncio.sleep(1800)
                continue

            # New session detected — scan!
            print(f"\n[AutoSignal] 🔔 {session_name} detected at {now.strftime('%H:%M UTC')}")

            await expire_old_signals()

            # Get relevant pairs for this session
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
                    await asyncio.sleep(5)
                    result = await analyze_pair(pair, timeframe)
                    if result:
                        saved = await save_auto_signal(result)
                        if saved:
                            signals_generated += 1

            print(f"[AutoSignal] ✅ {session_name} scan complete — {signals_generated} signals generated")
            last_session_scanned = session_name

        except Exception as e:
            print(f"[AutoSignal] Loop error: {e}")

        await asyncio.sleep(1800)  # check every 30 minutes