import httpx
from app.config import settings

async def send_telegram_message(message: str) -> bool:
    """Send a message to the configured Telegram chat."""
    print(f"[Telegram] Token: '{settings.TELEGRAM_BOT_TOKEN[:10]}...' Chat: '{settings.TELEGRAM_CHAT_ID}'")
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print("[Telegram] Bot token or chat ID not configured")
        return False
    
async def send_telegram_message(message: str) -> bool:
    """Send a message to the configured Telegram chat."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print("[Telegram] Bot token or chat ID not configured")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print(f"[Telegram] ✅ Message sent successfully")
                return True
            else:
                print(f"[Telegram] ❌ Failed: {response.text}")
                return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


async def send_signal_notification(signal_data: dict, pair: str, timeframe: str) -> None:
    """
    Send a formatted trading signal notification to Telegram.
    Called when the Auto Signal Engine finds a high-probability setup.
    """
    direction = signal_data.get("direction", "")
    confidence = signal_data.get("confidence_score", 0)
    current_price = signal_data.get("current_price", 0)
    entry_low = signal_data.get("entry_low", 0)
    entry_high = signal_data.get("entry_high", 0)
    stop_loss = signal_data.get("stop_loss", 0)
    tp1 = signal_data.get("take_profit_1", 0)
    tp2 = signal_data.get("take_profit_2", 0)
    tp3 = signal_data.get("take_profit_3", 0)
    rr_ratio = signal_data.get("rr_ratio", 0)
    explanation = signal_data.get("ai_explanation", "")
    risk_warning = signal_data.get("risk_warning", "")

    # Direction emoji
    if direction == "BUY":
        emoji = "🟢"
        action = "BUY (LONG)"
    elif direction == "SELL":
        emoji = "🔴"
        action = "SELL (SHORT)"
    else:
        return  # Don't send NO_TRADE notifications

    # Format price based on pair
    def fmt(price):
        if not price:
            return "N/A"
        if "JPY" in pair:
            return f"{price:.3f}"
        if "XAU" in pair:
            return f"{price:.2f}"
        return f"{price:.5f}"

    message = f"""
{emoji} <b>FOREX INTEL SIGNAL</b> {emoji}

<b>Pair:</b> {pair}
<b>Timeframe:</b> {timeframe}
<b>Direction:</b> {action}
<b>Confidence:</b> {confidence}%
<b>Current Price:</b> {fmt(current_price)}

📍 <b>ENTRY ZONE</b>
Between {fmt(entry_low)} — {fmt(entry_high)}

🛑 <b>STOP LOSS</b>
{fmt(stop_loss)}

🎯 <b>TAKE PROFITS</b>
TP1: {fmt(tp1)}
TP2: {fmt(tp2)}
TP3: {fmt(tp3)}

⚖️ <b>Risk:Reward:</b> 1:{rr_ratio}

🤖 <b>AI Analysis:</b>
{explanation}

⚠️ <b>Risk Warning:</b>
{risk_warning}

━━━━━━━━━━━━━━━━━━
⚠️ <i>Not financial advice. Always use proper risk management. Test on demo first.</i>
━━━━━━━━━━━━━━━━━━
"""

    await send_telegram_message(message.strip())


async def send_test_notification() -> bool:
    """Send a test message to verify Telegram is configured correctly."""
    message = """
🚀 <b>Forex Intel Bot Connected!</b>

Your Telegram notifications are set up correctly.

You will receive alerts here when:
✅ A high-probability signal is detected
✅ Confidence is 70%+ 
✅ Risk:Reward is 1.5+
✅ All indicators confirm the direction

The Auto Signal Engine scans at:
🕐 London Open (10:00 AM EAT)
🕒 New York Open (3:00 PM EAT)  
🕓 London/NY Overlap (3-7 PM EAT)
🕖 And other key sessions

⚠️ <i>Not financial advice. Always use demo account first.</i>
"""
    return await send_telegram_message(message.strip())