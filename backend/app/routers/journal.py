from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.trade import Trade
from app.schemas.trade import TradeCreate, TradeUpdate, TradeResponse, TradeStats
from app.services.alert_service import store_daily_risk
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
import uuid

router = APIRouter(prefix="/api/journal", tags=["Trade Journal"])


@router.get("", response_model=list[TradeResponse])
def get_trades(
    result: Optional[str] = Query(default=None),
    pair: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated list of user's trades with optional filters."""
    query = db.query(Trade).filter(Trade.user_id == current_user.id)

    if result:
        query = query.filter(Trade.result == result.upper())
    if pair:
        query = query.filter(Trade.pair == pair.upper().replace("-", "/"))

    trades = query.order_by(Trade.opened_at.desc()).offset(offset).limit(limit).all()
    return [TradeResponse.model_validate(t) for t in trades]


@router.post("", response_model=TradeResponse, status_code=201)
def create_trade(
    payload: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a new trade to the journal."""
    trade = Trade(
        user_id=current_user.id,
        signal_id=payload.signal_id,
        pair=payload.pair.upper().replace("-", "/"),
        direction=payload.direction.upper(),
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        lot_size=payload.lot_size,
        risk_amount=payload.risk_amount,
        ai_reason=payload.ai_reason,
        user_notes=payload.user_notes,
        result="OPEN",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    # Track daily risk exposure in Redis
    store_daily_risk(str(current_user.id), payload.risk_amount)

    return TradeResponse.model_validate(trade)


@router.get("/stats", response_model=TradeStats)
def get_trade_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get performance statistics for the current user."""
    trades = db.query(Trade).filter(Trade.user_id == current_user.id).all()

    total = len(trades)
    open_trades = sum(1 for t in trades if t.result == "OPEN")
    wins = sum(1 for t in trades if t.result == "WIN")
    losses = sum(1 for t in trades if t.result == "LOSS")
    closed = [t for t in trades if t.result in ["WIN", "LOSS", "BREAKEVEN"]]
    win_rate = round((wins / len(closed) * 100) if closed else 0, 1)
    total_pnl = round(sum(t.pnl or 0 for t in trades), 2)

    # Average R:R from closed trades
    rr_values = []
    for t in closed:
        risk = abs(t.entry_price - t.stop_loss)
        reward = abs(t.take_profit - t.entry_price)
        if risk > 0:
            rr_values.append(reward / risk)
    avg_rr = round(sum(rr_values) / len(rr_values), 2) if rr_values else 0.0

    return TradeStats(
        total_trades=total,
        open_trades=open_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_rr=avg_rr,
    )


@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(
    trade_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single trade by ID."""
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == current_user.id,
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    return TradeResponse.model_validate(trade)


@router.patch("/{trade_id}", response_model=TradeResponse)
def update_trade(
    trade_id: str,
    payload: TradeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a trade result, PnL, or notes."""
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == current_user.id,
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trade, field, value)

    db.commit()
    db.refresh(trade)

    return TradeResponse.model_validate(trade)


@router.delete("/{trade_id}")
def delete_trade(
    trade_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a trade from the journal."""
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == current_user.id,
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    db.delete(trade)
    db.commit()

    return {"message": "Trade deleted successfully."}