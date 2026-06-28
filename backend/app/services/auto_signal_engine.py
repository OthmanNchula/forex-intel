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

SCAN_TIMEFRAMES = ["M15", "H1", "H4"]

# Minimum thresholds for auto signal generation
MIN_CONFIDENCE = 55        # minimum AI confidence score
MIN_RR_RATIO = 1.2         # minimum risk to reward ratio
SCAN_INTERVAL = 300        # scan every 15 minutes (900 seconds)


def check_technical_confluence(indicators: dict, direction: str) -> tuple[bool, str]:
    """
    Check if all technical indicators confirm the trade direction.
    Returns (passes: bool, reason: str)
    """
    rsi = indicators.get("rsi", 50)
    macd_hist = indicators.get("macd_hist", 0)
    ema_cross = indicators.get("ema_cross", "BELOW")
    ema20_slope = indicators.get("ema20_slope", 0)
    trend = indicators.get("trend", "NEUTRAL")

    if direction == "BUY":
        # All must confirm bullish
        if ema_cross != "ABOVE":
            return False, "EMA20 is below EMA50 — no bullish trend"
        if rsi < 35 or rsi > 68:
            return False, f"RSI {rsi:.1f} not in buy zone (35-68)"
        if macd_hist < 0:
            return False, f"MACD histogram {macd_hist:.5f} is bearish"
        if ema20_slope < 0:
            return False, "EMA20 slope is falling — weak momentum"
        if trend == "BEARISH":
            return False, "Overall trend is bearish"
        return True, "All BUY conditions confirmed"

    elif direction == "SELL":
        # All must confirm bearish
        if ema_cross != "BELOW":
            return False, "EMA20 is above EMA50 — no bearish trend"
        if rsi > 65 or rsi < 32:
            return False, f"RSI {rsi:.1f} not in sell zone (32-65)"
        if macd_hist > 0:
            return False, f"MACD histogram {macd_hist:.5f} is bullish"
        if ema20_slope > 0:
            return False, "EMA20 slope is rising — weak bearish momentum"
        if trend == "BULLISH":
            return False, "Overall trend is bullish"
        return True, "All SELL conditions confirmed"

    return False, "Direction is NO_TRADE"


def signal_already_exists(db: Session, pair: str, timeframe: str) -> bool:
    """
    Check if a recent active signal already exists for this pair/timeframe.
    Avoids generating duplicate signals.
    """
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
    """
    Analyze a single pair on a single timeframe.
    Returns signal data if conditions are met, None otherwise.
    """
    try:
        # Step 1: Fetch market data
        df = await fetch_ohlcv(pair, timeframe, 200)
        if df is None:
            print(f"[AutoSignal] No data for {pair} {timeframe}")
            return None

        # Step 2: Compute indicators
        indicators = compute_all_indicators(df)
        if not indicators:
            print(f"[AutoSignal] Could not compute indicators for {pair} {timeframe}")
            return None

        # Step 3: Quick pre-check before calling AI
        # Only call AI if there's some directional bias
        rsi = indicators.get("rsi", 50)
        ema_cross = indicators.get("ema_cross", "")
        macd_hist = indicators.get("macd_hist", 0)

        # Determine likely direction from indicators
        bullish_points = 0
        bearish_points = 0

        if ema_cross == "ABOVE":
            bullish_points += 1
        else:
            bearish_points += 1

        if rsi > 50:
            bullish_points += 1
        else:
            bearish_points += 1

        if macd_hist > 0:
            bullish_points += 1
        else:
            bearish_points += 1

        # Skip if market is too mixed (not enough directional bias)
        if bullish_points == bearish_points:
            print(f"[AutoSignal] {pair} {timeframe} — mixed signals, skipping")
            return None

        # Step 4: Generate AI signal
        print(f"[AutoSignal] Analyzing {pair} {timeframe}...")
        ai_result = await generate_ai_signal(pair, timeframe, indicators)

        direction = ai_result.get("direction", "NO_TRADE")
        confidence = ai_result.get("confidence_score", 0)
        rr_ratio = ai_result.get("rr_ratio", 0)

        # Step 5: Check minimum thresholds
        if direction == "NO_TRADE":
            print(f"[AutoSignal] {pair} {timeframe} — AI says NO_TRADE")
            return None

        if confidence < MIN_CONFIDENCE:
            print(f"[AutoSignal] {pair} {timeframe} — confidence {confidence}% below minimum {MIN_CONFIDENCE}%")
            return None

        if rr_ratio and rr_ratio < MIN_RR_RATIO:
            print(f"[AutoSignal] {pair} {timeframe} — R:R {rr_ratio} below minimum {MIN_RR_RATIO}")
            return None

        # Step 6: Check technical confluence
        passes, reason = check_technical_confluence(indicators, direction)
        if not passes:
            print(f"[AutoSignal] {pair} {timeframe} — confluence failed: {reason}")
            return None

        # All checks passed!
        print(f"[AutoSignal] ✅ HIGH PROBABILITY SIGNAL: {pair} {timeframe} {direction} | Confidence: {confidence}% | R:R: {rr_ratio}")

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

        # Double-check no recent signal exists
        if signal_already_exists(db, pair, timeframe):
            print(f"[AutoSignal] Signal already exists for {pair} {timeframe}, skipping")
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

        # Cache signal in Redis
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

        print(f"[AutoSignal] 💾 Saved signal: {pair} {timeframe} {signal.direction} @ {signal.current_price}")
        return signal

    except Exception as e:
        print(f"[AutoSignal] Error saving signal: {e}")
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
        print(f"[AutoSignal] Error expiring signals: {e}")
    finally:
        db.close()


async def auto_signal_loop():
    """
    Main background loop — runs every 15 minutes.
    Scans all pairs and timeframes for high-probability setups.
    """
    print("[AutoSignal] 🚀 Auto Signal Engine started")
    print(f"[AutoSignal] Scanning {len(SCAN_PAIRS)} pairs on {len(SCAN_TIMEFRAMES)} timeframes every {SCAN_INTERVAL//60} minutes")
    print(f"[AutoSignal] Minimum confidence: {MIN_CONFIDENCE}% | Minimum R:R: {MIN_RR_RATIO}")

    # Wait 30 seconds on startup to let everything initialize
    await asyncio.sleep(30)

    while True:
        try:
            print(f"\n[AutoSignal] 🔍 Starting scan at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

            # Expire old signals first
            await expire_old_signals()

            signals_generated = 0

            # Scan each pair and timeframe
            for pair in SCAN_PAIRS:
                for timeframe in SCAN_TIMEFRAMES:
                    # Add delay between API calls to respect rate limits
                    await asyncio.sleep(3)

                    result = await analyze_pair(pair, timeframe)
                    if result:
                        saved = await save_auto_signal(result)
                        if saved:
                            signals_generated += 1

            print(f"[AutoSignal] ✅ Scan complete — {signals_generated} new signals generated")

        except Exception as e:
            print(f"[AutoSignal] Loop error: {e}")

        # Wait 15 minutes before next scan
        print(f"[AutoSignal] 💤 Next scan in {SCAN_INTERVAL//60} minutes")
        await asyncio.sleep(SCAN_INTERVAL)