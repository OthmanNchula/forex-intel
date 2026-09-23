import httpx
import os
from datetime import datetime, timezone


async def send_email(subject: str, html_content: str) -> bool:
    """
    Send an email using the Resend API.

    NOTIFICATION_EMAIL can hold a single address or a comma-separated list
    (e.g. "me@gmail.com, colleague@gmail.com") to notify multiple people.
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    raw_recipients = os.environ.get("NOTIFICATION_EMAIL", "")
    to_emails = [e.strip() for e in raw_recipients.split(",") if e.strip()]

    if not api_key or not to_emails:
        print("[Email] RESEND_API_KEY or NOTIFICATION_EMAIL not configured")
        return False

    payload = {
        "from": "Forex Intel <onboarding@resend.dev>",
        "to": to_emails,
        "subject": subject,
        "html": html_content,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code == 200:
                print(f"[Email] ✅ Email sent to {', '.join(to_emails)}")
                return True
            else:
                print(f"[Email] ❌ Failed: {response.text}")
                return False
    except Exception as e:
        print(f"[Email] Error: {e}")
        return False


async def send_signal_email(signal_data: dict, pair: str, timeframe: str) -> None:
    """Send a formatted signal notification email."""
    direction = signal_data.get("direction", "")
    if direction not in ["BUY", "SELL"]:
        return

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

    direction_color = "#22c55e" if direction == "BUY" else "#ef4444"
    direction_emoji = "🟢" if direction == "BUY" else "🔴"

    def fmt(price):
        if not price:
            return "N/A"
        if "JPY" in pair:
            return f"{price:.3f}"
        if "XAU" in pair:
            return f"{price:.2f}"
        return f"{price:.5f}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#0f1117;font-family:Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:20px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1B2A4A,#0E3460);border-radius:12px;padding:24px;text-align:center;margin-bottom:20px;">
    <h1 style="color:#C9A84C;margin:0;font-size:28px;">⚡ FOREX INTEL</h1>
    <p style="color:#94a3b8;margin:8px 0 0;">AI Trading Signal Alert</p>
  </div>

  <!-- Signal Badge -->
  <div style="background:#1e293b;border:2px solid {direction_color};border-radius:12px;padding:20px;text-align:center;margin-bottom:20px;">
    <div style="font-size:48px;margin-bottom:8px;">{direction_emoji}</div>
    <h2 style="color:{direction_color};margin:0;font-size:32px;font-weight:bold;">{direction}</h2>
    <p style="color:#e2e8f0;margin:8px 0 0;font-size:20px;font-weight:bold;">{pair} — {timeframe}</p>
    <p style="color:#94a3b8;margin:4px 0 0;font-size:14px;">{now}</p>
  </div>

  <!-- Confidence -->
  <div style="background:#1e293b;border-radius:12px;padding:16px;margin-bottom:16px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="color:#94a3b8;font-size:14px;">AI Confidence</span>
      <span style="color:{'#22c55e' if confidence >= 70 else '#f59e0b'};font-weight:bold;font-size:16px;">{confidence}%</span>
    </div>
    <div style="background:#374151;border-radius:4px;height:8px;">
      <div style="background:{'#22c55e' if confidence >= 70 else '#f59e0b'};width:{confidence}%;height:8px;border-radius:4px;"></div>
    </div>
  </div>

  <!-- Price Levels -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">

    <div style="background:#1e293b;border:1px solid #3b82f6;border-radius:12px;padding:16px;">
      <p style="color:#60a5fa;font-size:12px;margin:0 0 4px;font-weight:bold;">📍 ENTRY ZONE</p>
      <p style="color:#e2e8f0;font-size:14px;margin:0;font-family:monospace;">{fmt(entry_low)}<br>— {fmt(entry_high)}</p>
    </div>

    <div style="background:#1e293b;border:1px solid #ef4444;border-radius:12px;padding:16px;">
      <p style="color:#f87171;font-size:12px;margin:0 0 4px;font-weight:bold;">🛑 STOP LOSS</p>
      <p style="color:#e2e8f0;font-size:16px;margin:0;font-family:monospace;font-weight:bold;">{fmt(stop_loss)}</p>
    </div>

    <div style="background:#1e293b;border:1px solid #22c55e;border-radius:12px;padding:16px;">
      <p style="color:#4ade80;font-size:12px;margin:0 0 4px;font-weight:bold;">🎯 TAKE PROFIT 1</p>
      <p style="color:#e2e8f0;font-size:16px;margin:0;font-family:monospace;font-weight:bold;">{fmt(tp1)}</p>
    </div>

    <div style="background:#1e293b;border:1px solid #22c55e;border-radius:12px;padding:16px;">
      <p style="color:#4ade80;font-size:12px;margin:0 0 4px;font-weight:bold;">🎯 TAKE PROFIT 2</p>
      <p style="color:#e2e8f0;font-size:16px;margin:0;font-family:monospace;font-weight:bold;">{fmt(tp2)}</p>
    </div>

  </div>

  <!-- TP3 and RR -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
    <div style="background:#1e293b;border:1px solid #22c55e;border-radius:12px;padding:16px;">
      <p style="color:#4ade80;font-size:12px;margin:0 0 4px;font-weight:bold;">🎯 TAKE PROFIT 3</p>
      <p style="color:#e2e8f0;font-size:16px;margin:0;font-family:monospace;font-weight:bold;">{fmt(tp3)}</p>
    </div>
    <div style="background:#1e293b;border:1px solid #6366f1;border-radius:12px;padding:16px;">
      <p style="color:#a5b4fc;font-size:12px;margin:0 0 4px;font-weight:bold;">⚖️ RISK:REWARD</p>
      <p style="color:#e2e8f0;font-size:20px;margin:0;font-weight:bold;">1:{rr_ratio}</p>
    </div>
  </div>

  <!-- Current Price -->
  <div style="background:#1e293b;border-radius:12px;padding:16px;margin-bottom:16px;text-align:center;">
    <p style="color:#94a3b8;font-size:12px;margin:0 0 4px;">Current Price</p>
    <p style="color:#e2e8f0;font-size:24px;font-weight:bold;font-family:monospace;margin:0;">{fmt(current_price)}</p>
  </div>

  <!-- AI Analysis -->
  <div style="background:#1e293b;border:1px solid #1d4ed8;border-radius:12px;padding:16px;margin-bottom:16px;">
    <p style="color:#60a5fa;font-size:14px;font-weight:bold;margin:0 0 8px;">🤖 AI Analysis</p>
    <p style="color:#cbd5e1;font-size:14px;line-height:1.6;margin:0;">{explanation}</p>
  </div>

  <!-- Risk Warning -->
  <div style="background:#1e293b;border:1px solid #d97706;border-radius:12px;padding:16px;margin-bottom:16px;">
    <p style="color:#fbbf24;font-size:14px;font-weight:bold;margin:0 0 8px;">⚠️ Risk Warning</p>
    <p style="color:#fde68a;font-size:14px;line-height:1.6;margin:0;">{risk_warning}</p>
  </div>

  <!-- CTA Button -->
  <div style="text-align:center;margin-bottom:20px;">
    <a href="https://forex-intel-mu.vercel.app/signals" 
       style="background:#C9A84C;color:#1B2A4A;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;display:inline-block;">
      View Signal in App →
    </a>
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:16px;border-top:1px solid #374151;">
    <p style="color:#64748b;font-size:12px;margin:0;">
      ⚠️ This is NOT financial advice. Trading Forex involves significant risk of loss.<br>
      Always use proper risk management. Test on demo account first.<br><br>
      Forex Intel • AI Trading Intelligence Platform
    </p>
  </div>

</div>
</body>
</html>
"""

    subject = f"{direction_emoji} Forex Intel: {direction} Signal — {pair} ({confidence}% confidence)"
    await send_email(subject, html)


async def send_test_email() -> bool:
    """Send a test email to verify configuration."""
    html = """
<!DOCTYPE html>
<html>
<body style="background:#0f1117;font-family:Arial,sans-serif;padding:20px;">
<div style="max-width:600px;margin:0 auto;background:#1e293b;border-radius:12px;padding:32px;text-align:center;">
  <h1 style="color:#C9A84C;">⚡ Forex Intel</h1>
  <h2 style="color:#22c55e;">✅ Email Notifications Connected!</h2>
  <p style="color:#cbd5e1;">Your email notifications are working correctly.</p>
  <p style="color:#94a3b8;">You will receive signal alerts here when:<br>
  ✅ Confidence ≥ 70%<br>
  ✅ R:R ≥ 1.5<br>
  ✅ All indicators confirm direction</p>
  <a href="https://forex-intel-mu.vercel.app" 
     style="background:#C9A84C;color:#1B2A4A;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:16px;">
    Open Forex Intel →
  </a>
  <p style="color:#64748b;font-size:12px;margin-top:24px;">Not financial advice. Always use demo account first.</p>
</div>
</body>
</html>
"""
    return await send_email("✅ Forex Intel — Email Notifications Active!", html)