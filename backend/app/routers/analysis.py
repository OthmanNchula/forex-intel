from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.database import get_db
from app.models.signal import Signal
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.market_data import fetch_ohlcv
from app.services.indicator_engine import compute_all_indicators
from app.services.ai_analysis import generate_ai_signal
from app.services.alert_service import (
    cache_signal,
    get_cached_signal,
    get_daily_ai_call_count,
    get_monthly_ai_call_count,
)
from app.services.auto_signal_engine import (
    DAILY_AI_CALL_BUDGET,
    MONTHLY_AI_CALL_BUDGET,
    get_signal_expiry_hours,
)
from app.middleware.auth_middleware import get_current_user, verify_executor_key
from app.models.user import User

router = APIRouter(prefix="/api/analysis", tags=["AI Analysis"])


@router.get("/ai-usage")
def get_ai_usage(current_user: User = Depends(get_current_user)):
    """
    How many of today's and this month's AI analysis calls have been
    used, against the hard budgets in auto_signal_engine.py. Powers the
    usage indicator in the frontend so the daily/monthly caps aren't
    invisible — the same numbers the scanning engine itself checks
    before ever calling the AI.
    """
    daily_used = get_daily_ai_call_count()
    monthly_used = get_monthly_ai_call_count()
    return {
        "daily_used": daily_used,
        "daily_budget": DAILY_AI_CALL_BUDGET,
        "daily_remaining": max(0, DAILY_AI_CALL_BUDGET - daily_used),
        "monthly_used": monthly_used,
        "monthly_budget": MONTHLY_AI_CALL_BUDGET,
        "monthly_remaining": max(0, MONTHLY_AI_CALL_BUDGET - monthly_used),
    }


@router.post("/generate", response_model=SignalResponse)
async def generate_signal(
    payload: SignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a new AI trading signal for a pair.
    Checks Redis cache first to avoid repeated API calls.
    """
    pair = payload.pair.upper().replace("-", "/")
    timeframe = payload.timeframe

    # Check Redis cache first (signals cached for 5 minutes)
    cached = get_cached_signal(pair, timeframe)
    if cached:
        # Return cached signal as a mock Signal object
        return SignalResponse(**cached)

    # Step 1: Fetch OHLCV data
    df = await fetch_ohlcv(pair, timeframe, 200)
    if df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch market data for {pair}. Check the pair name."
        )

    # Step 2: Compute indicators
    indicators = compute_all_indicators(df)
    if not indicators:
        raise HTTPException(
            status_code=422,
            detail="Not enough historical data to compute indicators."
        )

    # Step 3: Generate AI signal
    ai_result = await generate_ai_signal(pair, timeframe, indicators, df)

    # Step 4: Save signal to database
    signal = Signal(
        pair=pair,
        timeframe=timeframe,
        direction=ai_result["direction"],
        current_price=ai_result["current_price"],
        entry_low=ai_result.get("entry_low"),
        entry_high=ai_result.get("entry_high"),
        stop_loss=ai_result.get("stop_loss"),
        take_profit_1=ai_result.get("take_profit_1"),
        take_profit_2=ai_result.get("take_profit_2"),
        take_profit_3=ai_result.get("take_profit_3"),
        rr_ratio=ai_result.get("rr_ratio"),
        confidence_score=ai_result.get("confidence_score"),
        ai_explanation=ai_result.get("ai_explanation"),
        risk_warning=ai_result.get("risk_warning"),
        ema20=ai_result.get("ema20"),
        ema50=ai_result.get("ema50"),
        rsi=ai_result.get("rsi"),
        macd_hist=ai_result.get("macd_hist"),
        atr=ai_result.get("atr"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=get_signal_expiry_hours(timeframe)),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    # Step 5: Cache the signal in Redis
    signal_dict = {
        "id": str(signal.id),
        "pair": signal.pair,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "current_price": signal.current_price,
        "entry_low": signal.entry_low,
        "entry_high": signal.entry_high,
        "stop_loss": signal.stop_loss,
        "take_profit_1": signal.take_profit_1,
        "take_profit_2": signal.take_profit_2,
        "take_profit_3": signal.take_profit_3,
        "rr_ratio": signal.rr_ratio,
        "confidence_score": signal.confidence_score,
        "ai_explanation": signal.ai_explanation,
        "risk_warning": signal.risk_warning,
        "ema20": signal.ema20,
        "ema50": signal.ema50,
        "rsi": signal.rsi,
        "macd_hist": signal.macd_hist,
        "atr": signal.atr,
        "is_active": signal.is_active,
        "created_at": signal.created_at.isoformat(),
    }
    cache_signal(pair, timeframe, signal_dict)

    return SignalResponse.model_validate(signal)


@router.get("/signals", response_model=list[SignalResponse])
def get_active_signals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all currently active signals."""
    signals = db.query(Signal).filter(
        Signal.is_active == True,
        Signal.direction != "NO_TRADE",
    ).order_by(Signal.created_at.desc()).limit(20).all()

    return [SignalResponse.model_validate(s) for s in signals]


# --- MT5 auto-execution bridge -------------------------------------------
#
# Called by the VPS-side executor script (mt5_executor/), not the frontend.
# Deliberately stricter than the notification filters in auto_signal_engine
# (confidence >= 62, R:R >= 1.5) — nothing double-checks these before real
# money moves, so the bar for "auto-executable" is higher than the bar for
# "worth alerting a human about".
#
# Registered here, BEFORE /signals/{signal_id} below: route matching is
# order-dependent, and a GET to /signals/executable would otherwise be
# swallowed by {signal_id} treating "executable" as an id.
EXECUTOR_MIN_CONFIDENCE = 65
EXECUTOR_MIN_RR_RATIO = 1.5


class MarkExecutedRequest(BaseModel):
    mt5_ticket: Optional[str] = None
    execution_price: Optional[float] = None
    execution_lot_size: Optional[float] = None
    note: str


@router.get("/signals/executable", response_model=list[SignalResponse])
def get_executable_signals(
    _: None = Depends(verify_executor_key),
    db: Session = Depends(get_db),
):
    """
    Active, not-yet-handled signals that clear the auto-execution bar.
    The executor polls this instead of /signals so it never sees a signal
    twice: once handled (filled OR deliberately skipped), the executor
    calls /signals/{id}/mark-executed, which excludes it here for good.
    """
    signals = db.query(Signal).filter(
        Signal.is_active == True,
        Signal.direction != "NO_TRADE",
        Signal.auto_executed == False,
        Signal.confidence_score >= EXECUTOR_MIN_CONFIDENCE,
        Signal.rr_ratio >= EXECUTOR_MIN_RR_RATIO,
    ).order_by(Signal.created_at.asc()).limit(20).all()

    return [SignalResponse.model_validate(s) for s in signals]


@router.get("/signals/{signal_id}", response_model=SignalResponse)
def get_signal(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific signal by ID."""
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found.")
    return SignalResponse.model_validate(signal)


@router.get("/signals/{pair}/latest", response_model=SignalResponse)
def get_latest_signal(
    pair: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the most recent signal for a specific pair."""
    pair = pair.upper().replace("-", "/")
    signal = db.query(Signal).filter(
        Signal.pair == pair,
        Signal.is_active == True,
    ).order_by(Signal.created_at.desc()).first()

    if not signal:
        raise HTTPException(
            status_code=404,
            detail=f"No active signal found for {pair}."
        )
    return SignalResponse.model_validate(signal)


@router.post("/signals/{signal_id}/mark-executed")
async def mark_signal_executed(
    signal_id: str,
    payload: MarkExecutedRequest,
    _: None = Depends(verify_executor_key),
    db: Session = Depends(get_db),
):
    """
    Records what the executor did with a signal — filled or skipped —
    and flags it so /signals/executable never returns it again. Called
    exactly once per signal by the executor, right after it either places
    the order or decides not to (stale entry, safety limit hit, etc).

    Also fires a Telegram message and email the moment this is recorded,
    so you find out a trade was taken (or skipped, and why) immediately
    instead of only discovering it later in executor.log or the MT5 app.
    """
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found.")

    signal.auto_executed = True
    signal.auto_executed_at = datetime.now(timezone.utc)
    signal.mt5_ticket = payload.mt5_ticket
    signal.execution_price = payload.execution_price
    signal.execution_lot_size = payload.execution_lot_size
    signal.execution_note = payload.note
    db.commit()

    # Best-effort notifications — the execution is already recorded above,
    # so a notification failure here must never make the executor think
    # its report failed (it would otherwise be retried/re-evaluated).
    try:
        from app.services.telegram_service import send_execution_notification
        await send_execution_notification(signal, payload)
    except Exception as e:
        print(f"[Executor] Telegram execution notification failed: {e}")

    try:
        from app.services.email_service import send_execution_email
        await send_execution_email(signal, payload, db)
    except Exception as e:
        print(f"[Executor] Email execution notification failed: {e}")

    return {"message": "Signal execution recorded."}


@router.post("/signals/{signal_id}/dismiss")
def dismiss_signal(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss/deactivate a signal."""
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found.")

    signal.is_active = False
    db.commit()

    return {"message": "Signal dismissed successfully."}