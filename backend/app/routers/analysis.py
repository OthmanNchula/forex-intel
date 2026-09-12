from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models.signal import Signal
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.market_data import fetch_ohlcv
from app.services.indicator_engine import compute_all_indicators
from app.services.ai_analysis import generate_ai_signal
from app.services.alert_service import cache_signal, get_cached_signal
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/analysis", tags=["AI Analysis"])


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
        expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
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