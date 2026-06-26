import json
from datetime import datetime, timezone
from typing import Optional

# Try to connect to Redis, but make it optional
try:
    from upstash_redis import Redis
    from app.config import settings

    redis_url = settings.UPSTASH_REDIS_REST_URL
    if redis_url and not redis_url.startswith("https://"):
        redis_url = f"https://{redis_url}"

    redis = Redis(
        url=redis_url,
        token=settings.UPSTASH_REDIS_REST_TOKEN,
    )
    REDIS_AVAILABLE = True
except Exception as e:
    print(f"Redis not available: {e}")
    redis = None
    REDIS_AVAILABLE = False

PRICE_CACHE_PREFIX = "price:"
SIGNAL_CACHE_PREFIX = "signal:"
ACTIVE_ALERTS_PREFIX = "alerts:user:"


def cache_price(pair: str, price: float, expire_seconds: int = 30) -> None:
    if not REDIS_AVAILABLE or redis is None:
        return
    try:
        key = f"{PRICE_CACHE_PREFIX}{pair.replace('/', '_')}"
        redis.setex(key, expire_seconds, str(price))
    except Exception:
        pass


def get_cached_price(pair: str) -> Optional[float]:
    if not REDIS_AVAILABLE or redis is None:
        return None
    try:
        key = f"{PRICE_CACHE_PREFIX}{pair.replace('/', '_')}"
        value = redis.get(key)
        return float(value) if value else None
    except Exception:
        return None


def cache_signal(pair: str, timeframe: str, signal_data: dict, expire_seconds: int = 300) -> None:
    if not REDIS_AVAILABLE or redis is None:
        return
    try:
        key = f"{SIGNAL_CACHE_PREFIX}{pair.replace('/', '_')}:{timeframe}"
        redis.setex(key, expire_seconds, json.dumps(signal_data))
    except Exception:
        pass


def get_cached_signal(pair: str, timeframe: str) -> Optional[dict]:
    if not REDIS_AVAILABLE or redis is None:
        return None
    try:
        key = f"{SIGNAL_CACHE_PREFIX}{pair.replace('/', '_')}:{timeframe}"
        value = redis.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def push_alert(user_id: str, alert_data: dict) -> None:
    if not REDIS_AVAILABLE or redis is None:
        return
    try:
        alert_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        key = f"{ACTIVE_ALERTS_PREFIX}{user_id}"
        redis.lpush(key, json.dumps(alert_data))
        redis.ltrim(key, 0, 49)
    except Exception:
        pass


def get_user_alerts(user_id: str, limit: int = 20) -> list:
    if not REDIS_AVAILABLE or redis is None:
        return []
    try:
        key = f"{ACTIVE_ALERTS_PREFIX}{user_id}"
        items = redis.lrange(key, 0, limit - 1)
        return [json.loads(item) for item in items] if items else []
    except Exception:
        return []


def check_price_alerts(pair: str, current_price: float, db_alerts: list) -> list:
    triggered = []
    for alert in db_alerts:
        if alert.is_triggered or alert.pair != pair:
            continue
        if alert.alert_type == "PRICE" and alert.condition_value:
            cached = get_cached_price(pair)
            if cached and (
                (cached < alert.condition_value <= current_price) or
                (cached > alert.condition_value >= current_price)
            ):
                triggered.append(alert)
    return triggered


def check_indicator_alerts(pair: str, indicators: dict, db_alerts: list) -> list:
    triggered = []
    rsi = indicators.get("rsi", 50)
    for alert in db_alerts:
        if alert.is_triggered or alert.pair != pair:
            continue
        if alert.alert_type == "RSI" and (rsi > 70 or rsi < 30):
            triggered.append(alert)
    return triggered


def store_daily_risk(user_id: str, risk_amount: float) -> float:
    if not REDIS_AVAILABLE or redis is None:
        return risk_amount
    try:
        key = f"daily_risk:{user_id}:{datetime.now(timezone.utc).date()}"
        current = redis.get(key)
        current_total = float(current) if current else 0.0
        new_total = current_total + risk_amount
        redis.setex(key, 86400, str(new_total))
        return new_total
    except Exception:
        return risk_amount


def get_daily_risk(user_id: str) -> float:
    if not REDIS_AVAILABLE or redis is None:
        return 0.0
    try:
        key = f"daily_risk:{user_id}:{datetime.now(timezone.utc).date()}"
        value = redis.get(key)
        return float(value) if value else 0.0
    except Exception:
        return 0.0