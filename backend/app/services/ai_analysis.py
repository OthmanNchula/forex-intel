import anthropic
import json
from typing import Optional
from app.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def build_analysis_prompt(
    pair: str,
    timeframe: str,
    indicators: dict,
) -> str:
    """Build the structured prompt to send to Claude."""

    current_price = indicators.get("current_price")
    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    ema_cross = indicators.get("ema_cross")
    rsi = indicators.get("rsi")
    macd_hist = indicators.get("macd_hist")
    atr = indicators.get("atr")
    trend = indicators.get("trend")
    volatility = indicators.get("volatility")
    nearest_support = indicators.get("nearest_support", "N/A")
    nearest_resistance = indicators.get("nearest_resistance", "N/A")

    return f"""
Analyze {pair} on the {timeframe} timeframe and provide a trading signal.

Current Market Data:
- Price: {current_price}
- EMA20: {ema20} | EMA50: {ema50} | EMA Cross: EMA20 is {ema_cross} EMA50
- RSI(14): {rsi}
- MACD Histogram: {macd_hist} (positive = bullish momentum, negative = bearish)
- ATR(14): {atr} (Volatility: {volatility})
- Trend: {trend}
- Nearest Support: {nearest_support}
- Nearest Resistance: {nearest_resistance}

Based on this data, provide your analysis as a JSON object with EXACTLY these fields:
{{
    "direction": "BUY" or "SELL" or "NO_TRADE",
    "entry_low": <float - lower bound of entry zone>,
    "entry_high": <float - upper bound of entry zone>,
    "stop_loss": <float - stop loss level>,
    "take_profit_1": <float - conservative target>,
    "take_profit_2": <float - main target>,
    "take_profit_3": <float - extended target>,
    "rr_ratio": <float - risk to reward ratio using TP2>,
    "confidence_score": <integer 0-100>,
    "explanation": "<2-3 sentences explaining the trade setup in simple language>",
    "risk_warning": "<1-2 sentences about the specific risks of this trade>"
}}

Rules:
- Use NO_TRADE if signals are mixed or unclear
- Stop loss must be beyond nearest support (BUY) or resistance (SELL)
- Take profits must be at realistic levels based on ATR
- Confidence score above 70 means strong signal, below 50 means weak
- Always mention the biggest risk factor in risk_warning
- Return ONLY the JSON object, no extra text
"""


def parse_ai_response(response_text: str) -> Optional[dict]:
    """
    Parse Claude's JSON response safely.
    Handles cases where Claude adds extra text around the JSON.
    """
    try:
        # Try direct parse first
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from within the text
    try:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            json_str = response_text[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    return None


def calculate_levels_from_indicators(indicators: dict, direction: str) -> dict:
    """
    Fallback level calculator if AI response is missing values.
    Uses ATR-based logic from the blueprint.
    """
    price = indicators["current_price"]
    atr = indicators["atr"]
    support = indicators.get("nearest_support")
    resistance = indicators.get("nearest_resistance")

    if direction == "BUY":
        entry_low = round(price - (0.3 * atr), 5)
        entry_high = round(price + (0.3 * atr), 5)
        stop_loss = round((support - (0.5 * atr)) if support else price - (1.5 * atr), 5)
        tp1 = round(price + (1.5 * atr), 5)
        tp2 = round(price + (2.5 * atr), 5)
        tp3 = round(price + (4.0 * atr), 5)
    else:  # SELL
        entry_low = round(price - (0.3 * atr), 5)
        entry_high = round(price + (0.3 * atr), 5)
        stop_loss = round((resistance + (0.5 * atr)) if resistance else price + (1.5 * atr), 5)
        tp1 = round(price - (1.5 * atr), 5)
        tp2 = round(price - (2.5 * atr), 5)
        tp3 = round(price - (4.0 * atr), 5)

    risk = abs(price - stop_loss)
    reward = abs(tp2 - price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "rr_ratio": rr,
    }


async def generate_ai_signal(
    pair: str,
    timeframe: str,
    indicators: dict,
) -> dict:
    """
    Main function — sends indicator data to Claude and returns
    a complete trading signal with all levels and explanation.
    """
    prompt = build_analysis_prompt(pair, timeframe, indicators)

    try:
        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system="""You are a professional forex trading analyst. 
You analyze technical indicator data and provide structured trading signals.
You NEVER guarantee profits. You always highlight risks.
You respond ONLY with valid JSON — no markdown, no explanation outside the JSON.""",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        response_text = message.content[0].text
        ai_result = parse_ai_response(response_text)

        if not ai_result:
            raise ValueError("Failed to parse AI response")

        # Ensure direction is valid
        direction = ai_result.get("direction", "NO_TRADE").upper()
        if direction not in ["BUY", "SELL", "NO_TRADE"]:
            direction = "NO_TRADE"

        # If direction is NO_TRADE, return minimal signal
        if direction == "NO_TRADE":
            return {
                "direction": "NO_TRADE",
                "current_price": indicators["current_price"],
                "entry_low": None,
                "entry_high": None,
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "take_profit_3": None,
                "rr_ratio": None,
                "confidence_score": ai_result.get("confidence_score", 30),
                "ai_explanation": ai_result.get(
                    "explanation",
                    "Market conditions are unclear. No trade recommended at this time."
                ),
                "risk_warning": ai_result.get(
                    "risk_warning",
                    "Wait for clearer market structure before entering."
                ),
                "ema20": indicators["ema20"],
                "ema50": indicators["ema50"],
                "rsi": indicators["rsi"],
                "macd_hist": indicators["macd_hist"],
                "atr": indicators["atr"],
            }

        # Use AI levels or fall back to ATR-calculated levels
        fallback = calculate_levels_from_indicators(indicators, direction)

        return {
            "direction": direction,
            "current_price": indicators["current_price"],
            "entry_low": ai_result.get("entry_low") or fallback["entry_low"],
            "entry_high": ai_result.get("entry_high") or fallback["entry_high"],
            "stop_loss": ai_result.get("stop_loss") or fallback["stop_loss"],
            "take_profit_1": ai_result.get("take_profit_1") or fallback["take_profit_1"],
            "take_profit_2": ai_result.get("take_profit_2") or fallback["take_profit_2"],
            "take_profit_3": ai_result.get("take_profit_3") or fallback["take_profit_3"],
            "rr_ratio": ai_result.get("rr_ratio") or fallback["rr_ratio"],
            "confidence_score": ai_result.get("confidence_score", 50),
            "ai_explanation": ai_result.get("explanation", "Analysis completed."),
            "risk_warning": ai_result.get(
                "risk_warning",
                "⚠️ This is not financial advice. Always use proper risk management."
            ),
            "ema20": indicators["ema20"],
            "ema50": indicators["ema50"],
            "rsi": indicators["rsi"],
            "macd_hist": indicators["macd_hist"],
            "atr": indicators["atr"],
        }

    except Exception as e:
        print(f"AI analysis error for {pair}: {e}")

        # Return a safe fallback signal on any error
        return {
            "direction": "NO_TRADE",
            "current_price": indicators.get("current_price", 0),
            "entry_low": None,
            "entry_high": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "take_profit_3": None,
            "rr_ratio": None,
            "confidence_score": 0,
            "ai_explanation": "AI analysis temporarily unavailable. Please try again.",
            "risk_warning": "⚠️ Always do your own analysis before trading.",
            "ema20": indicators.get("ema20"),
            "ema50": indicators.get("ema50"),
            "rsi": indicators.get("rsi"),
            "macd_hist": indicators.get("macd_hist"),
            "atr": indicators.get("atr"),
        }