"""
Candlestick pattern gate — Candlestick Trading Bible rules.

The rules engine decides the DIRECTION (regime, EMAs, RSI, MACD, higher
timeframe). This module decides WHEN to enter: only on a closed candle
that shows a rejection / momentum pattern in that direction, formed AT a
key level (swing support/resistance or a pullback to EMA20/EMA50).

A pattern in the middle of nowhere is ignored — that is the core rule of
the Bible approach.

Pure functions over the indicators dict, so they backtest without a
database or network. Needs these keys (added by compute_all_indicators):
    recent_candles  -> last 3 CLOSED candles, oldest first: [{open,high,low,close}, ...]
    swing_levels    -> confirmed swing highs/lows (no look-ahead)
    atr, ema20, ema50
"""
from typing import Optional

# ----------------------------------------------------------------- tuning
LEVEL_TOLERANCE_ATR = 0.5     # pattern extreme must be this close to a level
MIN_CANDLE_ATR = 0.3          # ignore tiny candles (noise)
MAX_CANDLE_ATR = 2.5          # ignore news spikes

# Patterns allowed to trigger a trade. Switch one off here if the
# backtest's per-pattern table shows it loses money.
ENABLED_PATTERNS = {
    "Pin bar",
    "Engulfing",
    "Morning/Evening star",
    "Tweezer",
    "Inside bar breakout",
}


def _parts(c: dict) -> dict:
    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    rng = h - l
    return {
        "o": o, "h": h, "l": l, "c": cl,
        "range": rng,
        "body": abs(cl - o),
        "upper": h - max(o, cl),
        "lower": min(o, cl) - l,
        "bull": cl > o,
        "bear": cl < o,
    }


# --------------------------------------------------------------- patterns
# Each returns True if the pattern is present in the given direction.

def _pin_bar(c3, direction):
    c = c3[-1]
    if c["range"] <= 0:
        return False
    small_body = c["body"] <= 0.33 * c["range"]
    if direction == "BUY":
        return small_body and c["lower"] >= 0.66 * c["range"] and c["upper"] <= 0.2 * c["range"]
    return small_body and c["upper"] >= 0.66 * c["range"] and c["lower"] <= 0.2 * c["range"]


def _engulfing(c3, direction):
    p, c = c3[-2], c3[-1]
    if c["body"] <= p["body"]:
        return False
    if direction == "BUY":
        return p["bear"] and c["bull"] and c["c"] > p["o"] and c["o"] <= p["c"]
    return p["bull"] and c["bear"] and c["c"] < p["o"] and c["o"] >= p["c"]


def _star(c3, direction):
    a, b, c = c3
    if a["range"] <= 0 or a["body"] < 0.6 * a["range"] or b["body"] > 0.35 * a["body"]:
        return False
    mid = (a["o"] + a["c"]) / 2
    if direction == "BUY":
        return a["bear"] and c["bull"] and c["c"] > mid
    return a["bull"] and c["bear"] and c["c"] < mid


def _tweezer(c3, direction, atr):
    p, c = c3[-2], c3[-1]
    tol = 0.1 * atr
    if direction == "BUY":
        return p["bear"] and c["bull"] and abs(c["l"] - p["l"]) <= tol
    return p["bull"] and c["bear"] and abs(c["h"] - p["h"]) <= tol


def _inside_bar_breakout(c3, direction):
    mother, inside, c = c3
    if not (inside["h"] < mother["h"] and inside["l"] > mother["l"]):
        return False
    return c["c"] > mother["h"] if direction == "BUY" else c["c"] < mother["l"]


def find_pattern(ind: dict, direction: str, allowed: Optional[set] = None) -> Optional[str]:
    """Name of the first enabled pattern found on the last closed candle, or None.
    `allowed` restricts the search further (the range playbook uses it)."""
    enabled = ENABLED_PATTERNS if allowed is None else (ENABLED_PATTERNS & allowed)
    raw = ind.get("recent_candles") or []
    if len(raw) < 3:
        return None
    c3 = [_parts(c) for c in raw[-3:]]
    atr = max(ind.get("atr", 0.0), 1e-9)

    checks = [
        ("Pin bar", lambda: _pin_bar(c3, direction)),
        ("Engulfing", lambda: _engulfing(c3, direction)),
        ("Morning/Evening star", lambda: _star(c3, direction)),
        ("Tweezer", lambda: _tweezer(c3, direction, atr)),
        ("Inside bar breakout", lambda: _inside_bar_breakout(c3, direction)),
    ]
    for name, fn in checks:
        if name in enabled and fn():
            return name
    return None


def pattern_extreme(ind: dict, direction: str) -> Optional[float]:
    """Lowest low (BUY) / highest high (SELL) of the 3-candle pattern area."""
    raw = ind.get("recent_candles") or []
    if not raw:
        return None
    return min(c["low"] for c in raw) if direction == "BUY" else max(c["high"] for c in raw)


def find_level(ind: dict, direction: str) -> Optional[str]:
    """Is the pattern sitting on a key level? Returns a description or None."""
    extreme = pattern_extreme(ind, direction)
    if extreme is None:
        return None
    atr = max(ind.get("atr", 0.0), 1e-9)
    tol = LEVEL_TOLERANCE_ATR * atr

    touching = [lvl for lvl in (ind.get("swing_levels") or []) if abs(extreme - lvl) <= tol]
    if touching:
        nearest = min(touching, key=lambda lvl: abs(extreme - lvl))
        kind = "support" if direction == "BUY" else "resistance"
        return f"{kind} {nearest:.5f}"
    for name in ("ema20", "ema50"):
        val = ind.get(name)
        if val is not None and abs(extreme - val) <= tol:
            return f"pullback to {name.upper()}"
    return None


def check_pattern_gate(ind: dict, direction: str, stop_atr: float) -> tuple[bool, str, Optional[str]]:
    """
    Final entry gate. Returns (passed, reason_text, pattern_name).

    Rules:
      1. The last closed candle is not tiny and not a news spike.
      2. A Bible pattern in the trade direction is present.
      3. It formed at a swing level or EMA20/EMA50.
      4. The pattern's extreme sits inside the ATR stop, so the stop is
         beyond the rejection — if price breaks it, the setup was wrong.
    """
    raw = ind.get("recent_candles") or []
    atr = max(ind.get("atr", 0.0), 1e-9)
    if len(raw) < 3:
        return False, "not enough candles for pattern check", None

    rng = raw[-1]["high"] - raw[-1]["low"]
    if rng < MIN_CANDLE_ATR * atr:
        return False, "last candle too small to read", None
    if rng > MAX_CANDLE_ATR * atr:
        return False, "last candle is a spike (news?)", None

    pattern = find_pattern(ind, direction)
    if pattern is None:
        return False, "no candlestick entry pattern", None

    level = find_level(ind, direction)
    if level is None:
        return False, f"{pattern} not at a key level", pattern

    price = ind.get("current_price", 0.0)
    extreme = pattern_extreme(ind, direction)
    if abs(price - extreme) >= stop_atr * atr:
        return False, f"{pattern} too large for a {stop_atr} ATR stop", pattern

    return True, f"{pattern} at {level}", pattern
