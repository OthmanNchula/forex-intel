"""
Rule-based signal engine — no AI, no per-call cost.

Decision flow for one pair/timeframe on a freshly closed candle:

  1. REGIME FILTER  — is the market trending or sideways? If it is
     sideways (or unclear), STAND ASIDE: no signal at all.
  2. DIRECTION      — EMA20 vs EMA50 gives the side; RSI, MACD and EMA
     slope must all agree (hard gates).
  3. HIGHER TIMEFRAME — if the next timeframe up clearly points the other
     way, stand aside; if it agrees, the score goes up.
  4. SCORE          — points for trend strength, EMA separation, a
     healthy RSI, clear room to the target and higher-timeframe support.
     The score becomes the signal's "confidence". It is a ranking of
     setup quality, NOT a measured win probability.
  5. LEVELS         — stop = 1.5 x ATR, take profit 2 = 3 x ATR, so the
     reward is always exactly 2x the risk.

Everything here is pure functions over an indicators dict (see
indicator_engine.compute_all_indicators), so it can be unit-tested and
backtested without a database or network.
"""
from typing import Optional

# ----------------------------------------------------------------- tuning
# Regime thresholds (all adjustable — the backtest script exists to tune these)
ADX_RANGING_BELOW = 20.0        # ADX under this = sideways
ADX_TRENDING_FROM = 22.0        # ADX at/above this (and no other flags) = trending
EMA_GAP_MIN_ATR = 0.30          # EMA20-EMA50 gap smaller than this = no real trend
EMA50_SLOPE_MIN_ATR = 0.25      # EMA50 moved less than this over 10 candles = flat
MAX_EMA_CROSSES_30 = 2          # more EMA20/50 crosses than this in 30 candles = whipsaw
MIN_RANGE_ATR_20 = 4.0          # last-20-candle box shorter than this = squeezed

# "UNCLEAR" regimes (one warning flag, or ADX between the two limits) may
# only trade with a stricter score.
UNCLEAR_MIN_SCORE = 75

# Execution levels, in ATR multiples. TP2 / SL = 2.0 -> fixed 2:1.
SL_ATR = 1.5
TP1_ATR = 2.25
TP2_ATR = 3.0
TP3_ATR = 3.75
FIXED_RR = TP2_ATR / SL_ATR  # 2.0

BASE_SCORE = 40
MAX_SCORE = 95
MIN_SCORE = 62               # same bar the executor uses (EXECUTOR_MIN_CONFIDENCE)


# ----------------------------------------------------------------- regime
def classify_regime(ind: dict) -> tuple[str, list[str]]:
    """
    Returns (regime, reasons) where regime is "TRENDING", "RANGING" or
    "UNCLEAR". `reasons` explains the verdict in plain words — it goes
    into the logs and the signal text so a skipped trade is never a
    mystery.
    """
    adx = ind.get("adx", 0.0)
    gap = ind.get("ema_gap_atr", 0.0)
    slope = abs(ind.get("ema50_slope_atr", 0.0))
    crosses = ind.get("ema_cross_count_30", 0)
    box = ind.get("range_atr_20", 99.0)

    flags = []
    if gap < EMA_GAP_MIN_ATR:
        flags.append(f"EMAs only {gap:.2f} ATR apart")
    if slope < EMA50_SLOPE_MIN_ATR:
        flags.append(f"EMA50 flat ({slope:.2f} ATR in 10 candles)")
    if crosses > MAX_EMA_CROSSES_30:
        flags.append(f"{crosses} EMA crosses in 30 candles")
    if box < MIN_RANGE_ATR_20:
        flags.append(f"price boxed in ({box:.1f} ATR range over 20 candles)")

    if adx < ADX_RANGING_BELOW:
        return "RANGING", [f"ADX {adx:.1f} below {ADX_RANGING_BELOW:.0f}"] + flags
    if len(flags) >= 2:
        return "RANGING", flags
    if adx >= ADX_TRENDING_FROM and not flags:
        return "TRENDING", [f"ADX {adx:.1f}, EMAs {gap:.2f} ATR apart, no whipsaw"]
    reasons = list(flags)
    if adx < ADX_TRENDING_FROM:
        reasons.insert(0, f"ADX {adx:.1f} borderline")
    return "UNCLEAR", reasons


# ------------------------------------------------------------- confluence
def check_confluence(ind: dict, direction: str) -> tuple[bool, str]:
    """Hard gates — every one must pass for the given direction."""
    rsi = ind.get("rsi", 50)
    macd_hist = ind.get("macd_hist", 0)
    ema_cross = ind.get("ema_cross", "")
    slope = ind.get("ema20_slope", 0)
    trend = ind.get("trend", "NEUTRAL")

    if direction == "BUY":
        if ema_cross != "ABOVE":
            return False, "EMA20 below EMA50"
        if rsi < 35 or rsi > 68:
            return False, f"RSI {rsi:.1f} outside buy zone 35-68"
        if macd_hist < 0:
            return False, "MACD histogram bearish"
        if slope < 0:
            return False, "EMA20 slope falling"
        if trend == "BEARISH":
            return False, "overall trend bearish"
        return True, "ok"

    if direction == "SELL":
        if ema_cross != "BELOW":
            return False, "EMA20 above EMA50"
        if rsi > 65 or rsi < 32:
            return False, f"RSI {rsi:.1f} outside sell zone 32-65"
        if macd_hist > 0:
            return False, "MACD histogram bullish"
        if slope > 0:
            return False, "EMA20 slope rising"
        if trend == "BULLISH":
            return False, "overall trend bullish"
        return True, "ok"

    return False, "no direction"


# ------------------------------------------------------------------ score
def score_setup(ind: dict, direction: str, htf_cross: Optional[str]) -> tuple[int, list[str]]:
    """
    Add up setup-quality points. Returns (score, breakdown_lines).
    `htf_cross` is the higher timeframe's EMA state ("ABOVE"/"BELOW") or
    None when it isn't available.
    """
    pts = BASE_SCORE
    notes = [f"base {BASE_SCORE}"]

    adx = ind.get("adx", 0.0)
    if adx >= 30:
        pts += 15; notes.append(f"strong trend ADX {adx:.0f} +15")
    elif adx >= 25:
        pts += 10; notes.append(f"good trend ADX {adx:.0f} +10")
    elif adx >= ADX_TRENDING_FROM:
        pts += 5; notes.append(f"trend ADX {adx:.0f} +5")

    gap = ind.get("ema_gap_atr", 0.0)
    if gap >= 0.8:
        pts += 10; notes.append(f"EMAs well separated ({gap:.1f} ATR) +10")
    elif gap >= 0.5:
        pts += 6; notes.append(f"EMAs separated ({gap:.1f} ATR) +6")

    rsi = ind.get("rsi", 50)
    if direction == "BUY":
        sweet = 50 <= rsi <= 62
    else:
        sweet = 38 <= rsi <= 50
    if sweet:
        pts += 10; notes.append(f"RSI {rsi:.0f} in sweet spot +10")
    else:
        pts += 4; notes.append(f"RSI {rsi:.0f} acceptable +4")

    slope_atr = abs(ind.get("ema20_slope", 0.0)) / max(ind.get("atr", 0.0), 1e-9)
    if slope_atr >= 0.3:
        pts += 5; notes.append("EMA20 slope strong +5")

    if htf_cross is not None:
        want = "ABOVE" if direction == "BUY" else "BELOW"
        if htf_cross == want:
            pts += 15; notes.append("higher timeframe agrees +15")

    # Room to the target: is the nearest opposing level beyond TP2?
    atr = max(ind.get("atr", 0.0), 1e-9)
    price = ind.get("current_price", 0.0)
    if direction == "BUY":
        level = ind.get("nearest_resistance")
        room = (level - price) / atr if level is not None else None
    else:
        level = ind.get("nearest_support")
        room = (price - level) / atr if level is not None else None
    if room is None or room >= TP2_ATR:
        pts += 10; notes.append("clear path to target +10")
    elif room >= 1.5:
        pts += 5; notes.append(f"{room:.1f} ATR room to nearest level +5")
    else:
        notes.append(f"nearest level only {room:.1f} ATR away +0")

    return min(pts, MAX_SCORE), notes


# ------------------------------------------------------------- main entry
def evaluate(
    pair: str,
    timeframe: str,
    ind: dict,
    htf_cross: Optional[str] = None,
    use_regime_filter: bool = True,
) -> dict:
    """
    Full decision for one closed candle. Always returns a dict:

      {"action": "TRADE", "signal": {...}, "regime": ..., ...}
      {"action": "STAND_ASIDE", "reason": "...", "regime": ...}

    `use_regime_filter=False` exists only so the backtest can measure
    what the filter is worth; production code leaves it on.
    """
    regime, regime_reasons = classify_regime(ind)
    regime_text = ", ".join(regime_reasons)

    if use_regime_filter and regime == "RANGING":
        return {"action": "STAND_ASIDE", "regime": regime,
                "reason": f"sideways market — {regime_text}"}

    direction = "BUY" if ind.get("ema_cross") == "ABOVE" else "SELL"
    ok, why = check_confluence(ind, direction)
    if not ok:
        return {"action": "STAND_ASIDE", "regime": regime, "reason": f"no setup — {why}"}

    if htf_cross is not None:
        opposing = "BELOW" if direction == "BUY" else "ABOVE"
        if htf_cross == opposing:
            return {"action": "STAND_ASIDE", "regime": regime,
                    "reason": "higher timeframe points the other way"}

    score, notes = score_setup(ind, direction, htf_cross)
    needed = MIN_SCORE
    if use_regime_filter and regime == "UNCLEAR":
        needed = UNCLEAR_MIN_SCORE
    if score < needed:
        return {"action": "STAND_ASIDE", "regime": regime, "score": score,
                "reason": f"score {score} below required {needed} ({regime.lower()} market)"}

    price = ind["current_price"]
    atr = ind["atr"]
    sign = 1 if direction == "BUY" else -1
    signal = {
        "direction": direction,
        "current_price": price,
        "entry_low": round(price - atr * 0.1, 5),
        "entry_high": round(price + atr * 0.1, 5),
        "stop_loss": round(price - sign * atr * SL_ATR, 5),
        "take_profit_1": round(price + sign * atr * TP1_ATR, 5),
        "take_profit_2": round(price + sign * atr * TP2_ATR, 5),
        "take_profit_3": round(price + sign * atr * TP3_ATR, 5),
        "rr_ratio": FIXED_RR,
        "confidence_score": score,
        "ai_explanation": (
            f"[RULES-BASED — no AI] {direction} on {pair} {timeframe}. Market regime: "
            f"{regime} ({regime_text}). Setup score {score}/100: " + "; ".join(notes) + ". "
            f"Stop {SL_ATR}x ATR, target {TP2_ATR}x ATR (fixed 2:1)."
        ),
        "risk_warning": (
            "Signal generated by fixed indicator rules, not a read of the chart: it cannot "
            "see news, candlestick patterns or sudden reversals. The score ranks setup "
            "quality; it is not a probability of winning. Trading Forex involves significant "
            "risk of loss."
        ),
        "ema20": ind.get("ema20"),
        "ema50": ind.get("ema50"),
        "rsi": ind.get("rsi"),
        "macd_hist": ind.get("macd_hist"),
        "atr": atr,
    }
    return {"action": "TRADE", "regime": regime, "score": score, "signal": signal}
