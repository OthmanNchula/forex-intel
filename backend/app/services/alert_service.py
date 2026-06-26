import json
from datetime import datetime, timezone
from typing import Optional
from upstash_redis import Redis
from app.config import settings

# Ensure URL has https:// prefix
redis_url = settings.UPSTASH_REDIS_REST_URL
if redis_url and not redis_url.startswith("https://"):
    redis_url = f"https://{redis_url}"

redis = Redis(
    url=redis_url,
    token=settings.UPSTASH_REDIS_REST_TOKEN,
)

# Redis key prefixes
PRICE_CACHE_PREFIX = "price:"
SIGNAL_CACHE_PREFIX = "signal:"
ALERT_QUEUE_KEY = "alert_queue"
ACTIVE_ALERTS_PREFIX = "alerts:user:"


def cache_price(pair: str, price: float, expire_seconds: int = 30) -> None:
    """Cache latest price for a pair in Redis."""
    key = f"{PRICE_CACHE_PREFIX}{pair.replace('/', '_')}"
    redis.setex(key, expire_seconds, str(price))


def get_cached_price(pair: str) -> Optional[float]:
    """Get cached price for a pair from Redis."""
    key = f"{PRICE_CACHE_PREFIX}{pair.replace('/', '_')}"
    value = redis.get(key)
    return float(value) if value else None


def cache_signal(pair: str, timeframe: str, signal_data: dict, expire_seconds: int = 300) -> None:
    """Cache a generated signal for 5 minutes to avoid repeated AI calls."""
    key = f"{SIGNAL_CACHE_PREFIX}{pair.replace('/', '_')}:{timeframe}"
    redis.setex(key, expire_seconds, json.dumps(signal_data))


def get_cached_signal(pair: str, timeframe: str) -> Optional[dict]:
    """Get cached signal from Redis if available."""
    key = f"{SIGNAL_CACHE_PREFIX}{pair.replace('/', '_')}:{timeframe}"
    value = redis.get(key)
    return json.loads(value) if value else None


def push_alert(user_id: str, alert_data: dict) -> None:
    """
    Push an alert notification to the user's alert queue in Redis.
    The WebSocket server reads from this queue and pushes to the client.
    """
    alert_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    key = f"{ACTIVE_ALERTS_PREFIX}{user_id}"
    redis.lpush(key, json.dumps(alert_data))
    # Keep only last 50 alerts per user
    redis.ltrim(key, 0, 49)


def get_user_alerts(user_id: str, limit: int = 20) -> list:
    """Get recent alert notifications for a user from Redis."""
    key = f"{ACTIVE_ALERTS_PREFIX}{user_id}"
    items = redis.lrange(key, 0, limit - 1)
    return [json.loads(item) for item in items] if items else []


def check_price_alerts(
    pair: str,
    current_price: float,
    db_alerts: list,
) -> list:
    """
    Check if any database alerts should be triggered
    based on the current price.

    Returns list of alerts that should fire.
    """
    triggered = []

    for alert in db_alerts:
        if alert.is_triggered:
            continue
        if alert.pair != pair:
            continue

        alert_type = alert.alert_type
        condition = alert.condition_value

        should_trigger = False

        if alert_type == "PRICE" and condition:
            # Trigger when price crosses the target level
            cached = get_cached_price(pair)
            if cached and (
                (cached < condition <= current_price) or
                (cached > condition >= current_price)
            ):
                should_trigger = True

        elif alert_type == "RSI":
            # Handled separately when indicators are computed
            pass

        elif alert_type == "EMA_CROSS":
            # Handled separately when indicators are computed
            pass

        if should_trigger:
            triggered.append(alert)

    return triggered


def check_indicator_alerts(
    pair: str,
    indicators: dict,
    db_alerts: list,
) -> list:
    """
    Check RSI and EMA crossover alerts against latest indicators.
    Returns list of alerts that should fire.
    """
    triggered = []
    rsi = indicators.get("rsi", 50)
    ema_cross = indicators.get("ema_cross")

    for alert in db_alerts:
        if alert.is_triggered or alert.pair != pair:
            continue

        should_trigger = False

        if alert.alert_type == "RSI":
            # Trigger when RSI enters overbought (>70) or oversold (<30)
            if rsi > 70 or rsi < 30:
                should_trigger = True

        elif alert.alert_type == "EMA_CROSS":
            # Trigger on any EMA crossover detected
            # In a full implementation this would compare previous cross state
            if ema_cross in ["ABOVE", "BELOW"]:
                should_trigger = True

        if should_trigger:
            triggered.append(alert)

    return triggered


def store_daily_risk(user_id: str, risk_amount: float) -> float:
    """
    Track cumulative daily risk exposure for a user.
    Resets automatically at midnight (TTL set to end of day).
    Returns new total daily risk.
    """
    key = f"daily_risk:{user_id}:{datetime.now(timezone.utc).date()}"
    current = redis.get(key)
    current_total = float(current) if current else 0.0
    new_total = current_total + risk_amount

    # Store with 24 hour expiry
    redis.setex(key, 86400, str(new_total))
    return new_total


def get_daily_risk(user_id: str) -> float:
    """Get today's total risk exposure for a user."""
    key = f"daily_risk:{user_id}:{datetime.now(timezone.utc).date()}"
    value = redis.get(key)
    return float(value) if value else 0.0