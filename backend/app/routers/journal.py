from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models.trade import Trade
from app.schemas.trade import TradeCreate, TradeUpdate, TradeResponse, TradeStats
from app.services.alert_service import store_daily_risk
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/journal", tags=["Trade Journal"])


# ---------------------------------------------------------------------------
# Pip value lookup — dollar value of 1 pip for 1 standard lot (1.0 lot)
# ---------------------------------------------------------------------------
PIP_VALUES = {
    "EUR/USD": 10.0,
    "GBP/USD": 10.0,
    "AUD/USD": 10.0,
    "NZD/USD": 10.0,
    "USD/CAD": 7.7,   # approx — depends on CAD/USD rate
    "USD/CHF": 10.0,
    "USD/JPY": 6.5,   # approx — depends on USD/JPY rate
    "XAU/USD": 1.0,   # Gold: 1 pip = $0.01 price move, $1 per 0.1 lot
}

PIP_SIZES = {
    "EUR/USD": 0.0001,
    "GBP/USD": 0.0001,
    "AUD/USD": 0.0001,
    "NZD/USD": 0.0001,
    "USD/CAD": 0.0001,
    "USD/CHF": 0.0001,
    "USD/JPY": 0.01,
    "XAU/USD": 0.01,   # Gold: 1 pip = $0.01
}


def calculate_pnl(pair: str, direction: str, entry: float, close: float, lots: float) -> float:
    """
    Calculate PnL correctly for each pair type.
    
    Formula:
    - Pips moved = |close - entry| / pip_size
    - PnL = pips * pip_value_per_lot * lots
    - Positive if trade went in correct direction, negative otherwise
    """
    pair = pair.upper()
    pip_size = PIP_SIZES.get(pair, 0.0001)
    pip_value_per_lot = PIP_VALUES.get(pair, 10.0)

    # Price difference
    price_diff = close - entry

    # Direction adjustment
    if direction.upper() == "BUY":
        signed_diff = price_diff      # positive = profit
    else:  # SELL
        signed_diff = -price_diff     # negative price move = profit

    # Calculate pips
    pips = signed_diff / pip_size

    # Calculate PnL
    pnl = pips * pip_value_per_lot * lots

    return round(pnl, 2)


def determine_result(direction: str, entry: float, close: float, stop_loss: float, take_profit: float) -> str:
    """Determine WIN/LOSS/BREAKEVEN based on close price."""
    if direction.upper() == "BUY":
        if close >= take_profit:
            return "WIN"
        elif close <= stop_loss:
            return "LOSS"
        elif abs(close - entry) < 0.0001 * entry:
            return "BREAKEVEN"
        elif close > entry:
            return "WIN"
        else:
            return "LOSS"
    else:  # SELL
        if close <= take_profit:
            return "WIN"
        elif close >= stop_loss:
            return "LOSS"
        elif abs(close - entry) < 0.0001 * entry:
            return "BREAKEVEN"
        elif close < entry:
            return "WIN"
        else:
            return "LOSS"


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

    store_daily_risk(str(current_user.id), payload.risk_amount)

    return TradeResponse.model_validate(trade)


@router.post("/{trade_id}/close", response_model=TradeResponse)
def close_trade(
    trade_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Close a trade with correct PnL calculation.
    Requires: { "close_price": float }
    Automatically calculates PnL and updates account balance.
    """
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == current_user.id,
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    if trade.result != "OPEN":
        raise HTTPException(status_code=400, detail="Trade is already closed.")

    close_price = payload.get("close_price")
    if not close_price:
        raise HTTPException(status_code=400, detail="close_price is required.")

    # Calculate PnL correctly
    pnl = calculate_pnl(
        pair=trade.pair,
        direction=trade.direction,
        entry=trade.entry_price,
        close=close_price,
        lots=trade.lot_size,
    )

    # Determine result
    result = determine_result(
        direction=trade.direction,
        entry=trade.entry_price,
        close=close_price,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
    )

    # Update trade
    trade.close_price = close_price
    trade.pnl = pnl
    trade.result = result
    trade.closed_at = datetime.now(timezone.utc)

    # Update account balance dynamically
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        current_balance = user.account_balance or 10000.0
        user.account_balance = round(current_balance + pnl, 2)
        print(f"[Journal] Balance updated: {current_balance} + {pnl} = {user.account_balance}")

    db.commit()
    db.refresh(trade)

    print(f"[Journal] Trade closed: {trade.pair} {trade.direction} | Entry: {trade.entry_price} | Close: {close_price} | PnL: {pnl} | Result: {result}")

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

    rr_values = []
    for t in closed:
        if t.stop_loss and t.take_profit and t.entry_price:
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
    """
    Update a trade. If close_price is provided, recalculates PnL correctly
    and updates account balance.
    """
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == current_user.id,
    ).first()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    update_data = payload.model_dump(exclude_unset=True)

    # If close_price is being set, recalculate PnL correctly
    close_price = update_data.get("close_price")
    if close_price and trade.result == "OPEN":
        # Calculate correct PnL
        correct_pnl = calculate_pnl(
            pair=trade.pair,
            direction=trade.direction,
            entry=trade.entry_price,
            close=close_price,
            lots=trade.lot_size,
        )
        update_data["pnl"] = correct_pnl

        # Auto-determine result if not provided
        if "result" not in update_data:
            update_data["result"] = determine_result(
                direction=trade.direction,
                entry=trade.entry_price,
                close=close_price,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
            )

        # Update account balance
        if "result" in update_data and update_data["result"] != "OPEN":
            user = db.query(User).filter(User.id == current_user.id).first()
            if user:
                old_balance = user.account_balance or 10000.0
                user.account_balance = round(old_balance + correct_pnl, 2)
                print(f"[Journal] Balance: {old_balance} + {correct_pnl} = {user.account_balance}")

        if not update_data.get("closed_at"):
            update_data["closed_at"] = datetime.now(timezone.utc)

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

    # Reverse balance effect if trade was closed
    if trade.result != "OPEN" and trade.pnl:
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            user.account_balance = round((user.account_balance or 10000.0) - trade.pnl, 2)

    db.delete(trade)
    db.commit()

    return {"message": "Trade deleted successfully."}
