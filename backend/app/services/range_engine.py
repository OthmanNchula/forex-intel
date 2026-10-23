"""
Range playbook — trades SIDEWAYS markets (mean reversion).

The trend playbook (rules_engine.evaluate) stands aside when the regime
filter says RANGING. Pairs that range a lot (EUR/USD, AUD/USD) therefore
rarely get a trade. This playbook trades exactly those periods, the way
the Candlestick Trading Bible describes range trading:

  1. REGIME   — the regime filter must say RANGING.
  2. BOX      — the 40-candle box must be wide enough for a 2:1 trade
                (at least RANGE_MIN_WIDTH_ATR).
  3. EDGE     — the rejection must happen at the box edge: the pattern's
                low within EDGE_TOLERANCE_ATR of the box bottom (BUY), or
                its high near the box top (SELL).
  4. STRETCH  — RSI was stretched in the last 3 candles (<= 35 for BUY,
                >= 65 for SELL).
  5. CANDLE   — a rejection candle in the trade direction: pin bar,
                engulfing, tweezer or morning/evening star. Breakout
                patterns are NOT used here (a breakout ends a range).
  6. LEVELS   — stop just beyond the pattern extreme (outside the box),
                target = 2 x risk, and the target must stay inside the
                box. Same fixed 2:1 as the trend playbook.

Pure functions over the indicators dict, like rules_engine.
"""
from typing import Optional

from app.services import candle_patterns, rules_engine

# ----------------------------------------------------------------- tuning
RANGE_MIN_WIDTH_ATR = 4.0      # box must be at least this tall
EDGE_TOLERANCE_ATR = 0.5       # pattern extreme this close to the box edge
STOP_BUFFER_ATR = 0.3          # stop this far beyond the pattern extreme
MIN_RISK_ATR = 0.5             # avoid stops so tight the spread eats them
MAX_RISK_ATR = 2.0             # avoid stops so wide the target leaves the box
TARGET_INSIDE_ATR = 0.2        # target must stay this far inside the far edge
RSI_BUY_MAX = 35
RSI_SELL_MIN = 65
RR = 2.0

RANGE_PATTERNS = {"Pin bar", "Engulfing", "Tweezer", "Morning/Evening star"}

BASE_SCORE = 62                # at the executor's bar; quality adds points
MAX_SCORE = 90


def _range_pattern(ind: dict, direction: str) -> Optional[str]:
    """First rejection pattern found, ignoring breakout patterns."""
    return candle_patterns.find_pattern(ind, direction, allowed=RANGE_PATTERNS)


def evaluate_range(pair: str, timeframe: str, ind: dict, regime: Optional[str] = None) -> dict:
    """Same return shape as rules_engine.evaluate."""
    if regime is None:
        regime, _ = rules_engine.classify_regime(ind)
    if regime != "RANGING":
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": "range playbook only trades sideways markets"}

    atr = max(ind.get("atr", 0.0), 1e-9)
    price = ind.get("current_price", 0.0)
    top, bottom = ind.get("range_high_40"), ind.get("range_low_40")
    candles = ind.get("recent_candles") or []
    if top is None or bottom is None or len(candles) < 3:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": "missing range data"}

    width = (top - bottom) / atr
    if width < RANGE_MIN_WIDTH_ATR:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": f"range only {width:.1f} ATR tall (need {RANGE_MIN_WIDTH_ATR:g})"}

    rng = candles[-1]["high"] - candles[-1]["low"]
    if rng > candle_patterns.MAX_CANDLE_ATR * atr:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": "last candle is a spike (news?)"}

    low3 = min(c["low"] for c in candles)
    high3 = max(c["high"] for c in candles)
    tol = EDGE_TOLERANCE_ATR * atr

    if low3 - bottom <= tol and ind.get("rsi_min_3", 50) <= RSI_BUY_MAX:
        direction, extreme = "BUY", low3
    elif top - high3 <= tol and ind.get("rsi_max_3", 50) >= RSI_SELL_MIN:
        direction, extreme = "SELL", high3
    else:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": "price not stretched at a range edge"}

    pattern = _range_pattern(ind, direction)
    if pattern is None:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": f"{direction} edge reached but no rejection candle"}

    sign = 1 if direction == "BUY" else -1
    stop = extreme - sign * STOP_BUFFER_ATR * atr
    risk = abs(price - stop)
    if risk < MIN_RISK_ATR * atr:
        risk = MIN_RISK_ATR * atr
        stop = price - sign * risk
    if risk > MAX_RISK_ATR * atr:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": f"stop would be {risk / atr:.1f} ATR wide"}

    target = price + sign * RR * risk
    far_edge = top if direction == "BUY" else bottom
    if sign * (far_edge - target) < TARGET_INSIDE_ATR * atr:
        return {"action": "STAND_ASIDE", "regime": regime, "playbook": "range",
                "reason": "2:1 target would be outside the range"}

    # Score: base at the executor bar, plus quality points
    score, notes = BASE_SCORE, [f"base {BASE_SCORE}"]
    rsi_ext = ind.get("rsi_min_3", 50) if direction == "BUY" else 100 - ind.get("rsi_max_3", 50)
    if rsi_ext <= 25:
        score += 8; notes.append("RSI deeply stretched +8")
    if pattern in ("Engulfing", "Morning/Evening star"):
        score += 6; notes.append(f"strong rejection ({pattern}) +6")
    if width >= 6:
        score += 6; notes.append(f"wide range ({width:.1f} ATR) +6")
    score = min(score, MAX_SCORE)

    signal = {
        "direction": direction,
        "current_price": price,
        "entry_low": round(price - atr * 0.1, 5),
        "entry_high": round(price + atr * 0.1, 5),
        "stop_loss": round(stop, 5),
        "take_profit_1": round(price + sign * 1.5 * risk, 5),
        "take_profit_2": round(target, 5),
        "take_profit_3": round(price + sign * min(2.5 * risk, abs(far_edge - price)), 5),
        "rr_ratio": RR,
        "confidence_score": score,
        "ai_explanation": (
            f"[RULES-BASED RANGE PLAYBOOK — no AI] {direction} on {pair} {timeframe}. "
            f"Sideways market, range {bottom:.5f}-{top:.5f} ({width:.1f} ATR). "
            f"{pattern} rejection at the range {'bottom' if sign == 1 else 'top'} with RSI stretched. "
            f"Score {score}: " + "; ".join(notes) + ". "
            f"Stop beyond the rejection, target 2x risk inside the range (fixed 2:1)."
        ),
        "risk_warning": (
            "Range trade: if the range breaks, the stop is hit. Signal generated by fixed "
            "rules; it cannot see news. The score ranks setup quality; it is not a "
            "probability of winning. Trading Forex involves significant risk of loss."
        ),
        "pattern": pattern,
        "ema20": ind.get("ema20"),
        "ema50": ind.get("ema50"),
        "rsi": ind.get("rsi"),
        "macd_hist": ind.get("macd_hist"),
        "atr": atr,
    }
    return {"action": "TRADE", "regime": regime, "score": score, "pattern": pattern,
            "playbook": "range", "signal": signal}
