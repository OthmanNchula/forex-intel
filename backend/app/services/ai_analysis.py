import anthropic
import json
from typing import Optional
from app.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def detect_candlestick_patterns(df) -> dict:
    """Detect key candlestick patterns from recent candles."""
    patterns = []

    if df is None or len(df) < 3:
        return {"patterns": ["No data"], "bias": "NEUTRAL"}

    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c  = df.iloc[-1]

    body        = abs(c['close'] - c['open'])
    upper_wick  = c['high'] - max(c['open'], c['close'])
    lower_wick  = min(c['open'], c['close']) - c['low']
    total_range = c['high'] - c['low']

    # Doji
    if total_range > 0 and body / total_range < 0.1:
        patterns.append("Doji (indecision)")

    # Hammer — small body at top, long lower wick
    if body > 0 and lower_wick >= 2 * body and upper_wick <= body * 0.5:
        patterns.append("Hammer (bullish reversal)")

    # Shooting Star — small body at bottom, long upper wick
    if body > 0 and upper_wick >= 2 * body and lower_wick <= body * 0.5:
        patterns.append("Shooting Star (bearish reversal)")

    # Bullish Engulfing
    if (c2['close'] < c2['open'] and
            c['close'] > c['open'] and
            c['open'] < c2['close'] and
            c['close'] > c2['open']):
        patterns.append("Bullish Engulfing (strong buy)")

    # Bearish Engulfing
    if (c2['close'] > c2['open'] and
            c['close'] < c['open'] and
            c['open'] > c2['close'] and
            c['close'] < c2['open']):
        patterns.append("Bearish Engulfing (strong sell)")

    # Morning Star
    if (c1['close'] < c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.3 and
            c['close'] > c['open'] and
            c['close'] > (c1['open'] + c1['close']) / 2):
        patterns.append("Morning Star (bullish reversal)")

    # Evening Star
    if (c1['close'] > c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.3 and
            c['close'] < c['open'] and
            c['close'] < (c1['open'] + c1['close']) / 2):
        patterns.append("Evening Star (bearish reversal)")

    if not patterns:
        patterns.append("No clear pattern")

    bullish = [p for p in patterns if any(w in p.lower() for w in ["bullish", "hammer", "morning"])]
    bearish = [p for p in patterns if any(w in p.lower() for w in ["bearish", "shooting", "evening"])]

    if len(bullish) > len(bearish):
        bias = "BULLISH"
    elif len(bearish) > len(bullish):
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {"patterns": patterns, "bias": bias}


def detect_market_structure(df) -> dict:
    """Detect uptrend / downtrend / ranging from swing highs and lows."""
    if df is None or len(df) < 20:
        return {"structure": "UNKNOWN", "description": "Not enough data"}

    highs = df['high'].values[-20:]
    lows  = df['low'].values[-20:]

    swing_highs, swing_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        hh = swing_highs[-1] > swing_highs[-2]
        hl = swing_lows[-1]  > swing_lows[-2]
        lh = swing_highs[-1] < swing_highs[-2]
        ll = swing_lows[-1]  < swing_lows[-2]

        if hh and hl:
            return {"structure": "UPTREND",   "description": "Higher highs and higher lows — bullish market structure"}
        if lh and ll:
            return {"structure": "DOWNTREND", "description": "Lower highs and lower lows — bearish market structure"}
        return {"structure": "RANGING",   "description": "Mixed swing points — sideways/ranging market"}

    return {"structure": "UNKNOWN", "description": "Cannot determine structure clearly"}


def get_rsi_momentum(df, indicators: dict) -> dict:
    """Check if RSI momentum is rising or falling."""
    rsi = indicators.get("rsi", 50)
    if df is None or len(df) < 5:
        return {"direction": "UNKNOWN", "strength": "WEAK"}

    closes = df['close'].values
    price_now = closes[-1]
    price_ago = closes[-4]

    if rsi > 55 and price_now > price_ago:
        return {"direction": "RISING",  "strength": "STRONG" if rsi > 60 else "MODERATE"}
    if rsi < 45 and price_now < price_ago:
        return {"direction": "FALLING", "strength": "STRONG" if rsi < 40 else "MODERATE"}
    return {"direction": "FLAT", "strength": "WEAK"}


def get_macd_momentum(indicators: dict) -> dict:
    """Check MACD histogram direction and strength."""
    h = indicators.get("macd_hist", 0)
    if h > 0.0002:
        return {"direction": "BULLISH", "strength": "STRONG"}
    if h > 0:
        return {"direction": "BULLISH", "strength": "WEAK"}
    if h < -0.0002:
        return {"direction": "BEARISH", "strength": "STRONG"}
    if h < 0:
        return {"direction": "BEARISH", "strength": "WEAK"}
    return {"direction": "NEUTRAL", "strength": "FLAT"}


def check_sr_proximity(indicators: dict) -> dict:
    """Warn when price is within 0.5 ATR of a key S/R level."""
    price = indicators.get("current_price", 0)
    support    = indicators.get("nearest_support", 0)
    resistance = indicators.get("nearest_resistance", 0)
    atr = indicators.get("atr", 0)

    if not price or not atr:
        return {"near_support": False, "near_resistance": False, "warning": ""}

    near_sup = bool(support    and abs(price - support)    < atr * 0.5)
    near_res = bool(resistance and abs(price - resistance) < atr * 0.5)

    warning = ""
    if near_res:
        warning = f"Price is near resistance {resistance:.5f} — may cap upside"
    elif near_sup:
        warning = f"Price is near support {support:.5f} — may provide buying opportunity"

    return {"near_support": near_sup, "near_resistance": near_res, "warning": warning}

def build_analysis_prompt(
    pair: str,
    timeframe: str,
    indicators: dict,
    df=None,
) -> str:
    """Build the enhanced structured prompt to send to Claude."""
    print(f"[AI Analysis] df received: {df is not None}, rows: {len(df) if df is not None else 0}")
    
    current_price     = indicators.get("current_price")
    ema20             = indicators.get("ema20")
    ema50             = indicators.get("ema50")
    ema_cross         = indicators.get("ema_cross")
    rsi               = indicators.get("rsi")
    macd_hist         = indicators.get("macd_hist")
    atr               = indicators.get("atr")
    trend             = indicators.get("trend")
    volatility        = indicators.get("volatility")
    nearest_support   = indicators.get("nearest_support", "N/A")
    nearest_resistance = indicators.get("nearest_resistance", "N/A")

    # Enhanced analysis
    candle   = detect_candlestick_patterns(df)
    structure = detect_market_structure(df)
    rsi_mom  = get_rsi_momentum(df, indicators)
    macd_mom = get_macd_momentum(indicators)
    sr_prox  = check_sr_proximity(indicators)

    sr_warn = f"\n- ⚠️ WARNING: {sr_prox['warning']}" if sr_prox['warning'] else ""

    return f"""Analyze {pair} on the {timeframe} timeframe and provide a trading signal.

## Current Market Data
- Price: {current_price}
- EMA20: {ema20} | EMA50: {ema50} | EMA Cross: EMA20 is {ema_cross} EMA50
- RSI(14): {rsi}
- MACD Histogram: {macd_hist} (positive = bullish momentum, negative = bearish)
- ATR(14): {atr} (Volatility: {volatility})
- Trend: {trend}
- Nearest Support: {nearest_support}
- Nearest Resistance: {nearest_resistance}{sr_warn}

## Advanced Technical Analysis
### Candlestick Patterns (last 3 candles)
- Patterns detected: {', '.join(candle['patterns'])}
- Pattern bias: {candle['bias']}

### Market Structure (last 20 candles)
- Structure: {structure['structure']}
- Detail: {structure['description']}

### Momentum
- RSI momentum: {rsi_mom['direction']} ({rsi_mom['strength']})
- MACD momentum: {macd_mom['direction']} ({macd_mom['strength']})

## Signal Rules — use ALL of the following
1. EMA cross direction (primary trend filter)
2. RSI zone: 35-68 for BUY, 32-65 for SELL — do NOT enter if overbought/oversold
3. MACD histogram direction (momentum confirmation)
4. Candlestick pattern bias
5. Market structure (uptrend favors BUY, downtrend favors SELL)
6. Avoid entries right at resistance (BUY) or at support (SELL)

## Level Calculation
- BUY: entry_low = price - 0.3*ATR, entry_high = price + 0.3*ATR, SL = price - 1.5*ATR
- SELL: entry_low = price - 0.3*ATR, entry_high = price + 0.3*ATR, SL = price + 1.5*ATR
- TP1 = ±1.5*ATR, TP2 = ±2.5*ATR, TP3 = ±4.0*ATR

Based on this data, provide your analysis as a JSON object with EXACTLY these fields:
{{
    "direction": "BUY" or "SELL" or "NO_TRADE",
    "entry_low": <float>,
    "entry_high": <float>,
    "stop_loss": <float>,
    "take_profit_1": <float>,
    "take_profit_2": <float>,
    "take_profit_3": <float>,
    "rr_ratio": <float - risk to reward ratio using TP2>,
    "confidence_score": <integer 0-100>,
    "explanation": "<2-3 sentences explaining the signal, mentioning candlestick patterns and market structure>",
    "risk_warning": "<1-2 sentences about specific risks including any S/R levels nearby>"
}}

Rules:
- Use NO_TRADE if signals are mixed or unclear
- Stop loss must be beyond nearest support (BUY) or resistance (SELL)
- Confidence above 70 = strong signal, below 50 = weak
- Return ONLY the JSON object, no extra text
"""


def parse_ai_response(response_text: str) -> Optional[dict]:
    """Parse Claude's JSON response safely."""
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    try:
        start = response_text.find("{")
        end   = response_text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
    except json.JSONDecodeError:
        pass

    return None


def calculate_levels_from_indicators(indicators: dict, direction: str) -> dict:
    """Fallback level calculator using ATR-based logic."""
    price      = indicators["current_price"]
    atr        = indicators["atr"]
    support    = indicators.get("nearest_support")
    resistance = indicators.get("nearest_resistance")

    if direction == "BUY":
        entry_low  = round(price - 0.3 * atr, 5)
        entry_high = round(price + 0.3 * atr, 5)
        stop_loss  = round((support - 0.5 * atr) if support else price - 1.5 * atr, 5)
        tp1 = round(price + 1.5 * atr, 5)
        tp2 = round(price + 2.5 * atr, 5)
        tp3 = round(price + 4.0 * atr, 5)
    else:
        entry_low  = round(price - 0.3 * atr, 5)
        entry_high = round(price + 0.3 * atr, 5)
        stop_loss  = round((resistance + 0.5 * atr) if resistance else price + 1.5 * atr, 5)
        tp1 = round(price - 1.5 * atr, 5)
        tp2 = round(price - 2.5 * atr, 5)
        tp3 = round(price - 4.0 * atr, 5)

    risk   = abs(price - stop_loss)
    reward = abs(tp2 - price)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    return {
        "entry_low": entry_low, "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit_1": tp1, "take_profit_2": tp2, "take_profit_3": tp3,
        "rr_ratio": rr,
    }


async def generate_ai_signal(
    pair: str,
    timeframe: str,
    indicators: dict,
    df=None,
) -> dict:
    """
    Main function — sends enriched indicator data to Claude and returns
    a complete trading signal with entry, SL, TP and explanation.
    Now includes candlestick patterns, market structure, and momentum analysis.
    """
    prompt = build_analysis_prompt(pair, timeframe, indicators, df)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system="""You are a professional forex trading analyst.
You analyze technical indicator data and provide structured trading signals.
You NEVER guarantee profits. You always highlight risks.
You respond ONLY with valid JSON — no markdown, no explanation outside the JSON.""",
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        ai_result = parse_ai_response(response_text)

        if not ai_result:
            raise ValueError("Failed to parse AI response")

        direction = ai_result.get("direction", "NO_TRADE").upper()
        if direction not in ["BUY", "SELL", "NO_TRADE"]:
            direction = "NO_TRADE"

        if direction == "NO_TRADE":
            return {
                "direction": "NO_TRADE",
                "current_price": indicators["current_price"],
                "entry_low": None, "entry_high": None,
                "stop_loss": None,
                "take_profit_1": None, "take_profit_2": None, "take_profit_3": None,
                "rr_ratio": None,
                "confidence_score": ai_result.get("confidence_score", 30),
                "ai_explanation": ai_result.get("explanation", "Market conditions are unclear. No trade recommended."),
                "risk_warning": ai_result.get("risk_warning", "Wait for clearer market structure before entering."),
                "ema20": indicators["ema20"], "ema50": indicators["ema50"],
                "rsi": indicators["rsi"], "macd_hist": indicators["macd_hist"],
                "atr": indicators["atr"],
            }

        fallback = calculate_levels_from_indicators(indicators, direction)

        return {
            "direction": direction,
            "current_price": indicators["current_price"],
            "entry_low":      ai_result.get("entry_low")      or fallback["entry_low"],
            "entry_high":     ai_result.get("entry_high")     or fallback["entry_high"],
            "stop_loss":      ai_result.get("stop_loss")      or fallback["stop_loss"],
            "take_profit_1":  ai_result.get("take_profit_1")  or fallback["take_profit_1"],
            "take_profit_2":  ai_result.get("take_profit_2")  or fallback["take_profit_2"],
            "take_profit_3":  ai_result.get("take_profit_3")  or fallback["take_profit_3"],
            "rr_ratio":       ai_result.get("rr_ratio")       or fallback["rr_ratio"],
            "confidence_score": ai_result.get("confidence_score", 50),
            "ai_explanation": ai_result.get("explanation", "Analysis completed."),
            "risk_warning":   ai_result.get("risk_warning", "⚠️ Not financial advice. Always use proper risk management."),
            "ema20": indicators["ema20"], "ema50": indicators["ema50"],
            "rsi": indicators["rsi"], "macd_hist": indicators["macd_hist"],
            "atr": indicators["atr"],
        }

    except Exception as e:
        print(f"AI analysis error for {pair}: {e}")
        return {
            "direction": "NO_TRADE",
            "current_price": indicators.get("current_price", 0),
            "entry_low": None, "entry_high": None,
            "stop_loss": None,
            "take_profit_1": None, "take_profit_2": None, "take_profit_3": None,
            "rr_ratio": None,
            "confidence_score": 0,
            "ai_explanation": "AI analysis temporarily unavailable. Please try again.",
            "risk_warning": "⚠️ Always do your own analysis before trading.",
            "ema20": indicators.get("ema20"), "ema50": indicators.get("ema50"),
            "rsi": indicators.get("rsi"), "macd_hist": indicators.get("macd_hist"),
            "atr": indicators.get("atr"),
        }
