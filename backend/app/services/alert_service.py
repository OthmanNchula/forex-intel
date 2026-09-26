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
ANALYSIS_COOLDOWN_PREFIX = "analyzed:"


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


def was_recently_analyzed(
    pair: str,
    timeframe: str,
    direction: str,
    price: float,
    atr: float,
    price_move_atr_multiple: float = 1.0,
) -> bool:
    """
    True if this pair/timeframe was already analyzed within the cooldown
    window AND nothing meaningful has changed since — same directional
    lean, AND price hasn't moved far enough to represent a genuinely
    different setup (different entry/stop/target).

    This is deliberately NOT just "have we seen this pair/timeframe
    recently" — that would also skip a real reversal (bullish -> bearish)
    or a real breakout (still bullish, but price has run far enough that
    the entry/stop/target are all different now). Both of those should
    still get analyzed even mid-cooldown.

    "Moved far enough" is measured in the pair's own ATR (its typical
    recent move size), not raw price or pips, so the threshold scales
    correctly for both a JPY pair and Gold. Default: a move of one full
    ATR since the last check counts as a new setup.

    Backed by Redis (Upstash) so it's shared across processes — critical
    because the standalone Railway Cron job (cron_scan.py) spins up a
    fresh process on every fire with no in-memory state of its own, so
    an in-memory dict would never dedupe across cron invocations the way
    it can across in-process loop ticks.

    If Redis is unavailable, or anything about the stored record looks
    off, this fails OPEN (returns False, i.e. "go ahead and analyze") —
    worse case is a duplicate AI call, never a missed signal.
    """
    if not REDIS_AVAILABLE or redis is None:
        return False
    try:
        key = f"{ANALYSIS_COOLDOWN_PREFIX}{pair.replace('/', '_')}:{timeframe}"
        raw = redis.get(key)
        if raw is None:
            return False

        last = json.loads(raw)
        last_direction = last.get("direction")
        last_price = last.get("price")

        if last_direction != direction:
            return False  # direction flipped — always treat as new

        if last_price is None or not atr:
            return False  # missing data — fail open, analyze it

        price_moved = abs(price - last_price)
        threshold = atr * price_move_atr_multiple
        if price_moved >= threshold:
            return False  # moved far enough to be a different setup

        return True  # same pair, timeframe, direction, and no material price move
    except Exception:
        return False


def mark_analyzed(
    pair: str,
    timeframe: str,
    direction: str,
    price: float,
    cooldown_seconds: int = 3600,
) -> None:
    """Record what this pair/timeframe looked like when it was just
    analyzed by AI (direction + price), so repeated cron fires or
    overlapping schedulers can tell a real repeat apart from a
    reversal or a breakout to a materially different price."""
    if not REDIS_AVAILABLE or redis is None:
        return
    try:
        key = f"{ANALYSIS_COOLDOWN_PREFIX}{pair.replace('/', '_')}:{timeframe}"
        value = json.dumps({"direction": direction, "price": price})
        redis.setex(key, cooldown_seconds, value)
    except Exception:
        pass


AI_CALL_BUDGET_PREFIX = "ai_calls:"


def _current_month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_monthly_ai_call_count() -> int:
    """How many AI analysis calls have been made so far this UTC month."""
    if not REDIS_AVAILABLE or redis is None:
        return 0
    try:
        key = f"{AI_CALL_BUDGET_PREFIX}{_current_month_key()}"
        value = redis.get(key)
        return int(value) if value else 0
    except Exception:
        return 0


def is_within_ai_call_budget(monthly_budget: int) -> bool:
    """
    True if this month's AI call count is still under the budget. This is
    the hard spending cap — unlike the cooldown/session-window tuning,
    which only reduces AVERAGE cost, this is what actually guarantees a
    ceiling regardless of how volatile the market gets. When it returns
    False, the caller should NOT call the AI at all this month (a
    technical-only fallback can still run — see auto_signal_engine.py).

    Fails OPEN (returns True, i.e. "still within budget") if Redis is
    unreachable. This does mean a Redis outage could let calls through
    uncapped for as long as the outage lasts — a real trade-off, but the
    alternative (fail closed) would silently stop ALL signals, AI and
    technical-only alike, on every Redis hiccup, which is worse for a
    home-grown trading tool than a rare, short-lived overspend risk.
    """
    if not REDIS_AVAILABLE or redis is None:
        return True
    try:
        return get_monthly_ai_call_count() < monthly_budget
    except Exception:
        return True


def increment_monthly_ai_call_count() -> int:
    """Record one AI call against this month's budget. Call this right
    before making the AI call (same reasoning as mark_analyzed — count it
    before it happens, so two near-simultaneous callers can't both slip
    through under the wire)."""
    if not REDIS_AVAILABLE or redis is None:
        return 0
    try:
        key = f"{AI_CALL_BUDGET_PREFIX}{_current_month_key()}"
        new_count = redis.incr(key)
        if new_count == 1:
            # First call this month — set the key to expire in ~40 days
            # so it's naturally gone well before the same month name
            # comes around next year, without needing a cron to reset it.
            redis.expire(key, 40 * 86400)
        return new_count
    except Exception:
        return 0


def _current_day_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_daily_ai_call_count() -> int:
    """How many AI analysis calls have been made so far today (UTC)."""
    if not REDIS_AVAILABLE or redis is None:
        return 0
    try:
        key = f"{AI_CALL_BUDGET_PREFIX}day:{_current_day_key()}"
        value = redis.get(key)
        return int(value) if value else 0
    except Exception:
        return 0


def is_within_daily_ai_call_budget(daily_budget: int) -> bool:
    """
    True if today's AI call count is still under the daily budget. This
    spreads MONTHLY_AI_CALL_BUDGET evenly across the days of the month,
    so a single volatile day (or week) can't burn through the whole
    month's budget in one go, leaving nothing but technical-only
    fallback signals for the remaining weeks. Once today's slice is
    used up, the engine falls back to technical-only signals for the
    rest of today specifically and picks back up with the AI tomorrow —
    "wait for tomorrow" as requested, not "wait for next month."

    Same fail-open behavior as is_within_ai_call_budget() and the same
    reasoning: a Redis outage should not silently stop every signal.
    """
    if not REDIS_AVAILABLE or redis is None:
        return True
    try:
        return get_daily_ai_call_count() < daily_budget
    except Exception:
        return True


def increment_daily_ai_call_count() -> int:
    """Record one AI call against today's slice of the monthly budget.
    Expires in 2 days so stale keys don't pile up in Redis."""
    if not REDIS_AVAILABLE or redis is None:
        return 0
    try:
        key = f"{AI_CALL_BUDGET_PREFIX}day:{_current_day_key()}"
        new_count = redis.incr(key)
        if new_count == 1:
            redis.expire(key, 2 * 86400)
        return new_count
    except Exception:
        return 0


def get_daily_risk(user_id: str) -> float:
    if not REDIS_AVAILABLE or redis is None:
        return 0.0
    try:
        key = f"daily_risk:{user_id}:{datetime.now(timezone.utc).date()}"
        value = redis.get(key)
        return float(value) if value else 0.0
    except Exception:
        return 0.0