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
    # Normalize the same way create_trade() normalizes before storing
    # ("XAU-USD", "xau/usd", or trailing/leading whitespace all need to
    # land on the same "XAU/USD" key) — otherwise this silently misses
    # the dict and falls back to the FX-pair defaults (0.0001 / $10),
    # which for XAU/USD is a 1000x PnL inflation (100x pip size x 10x
    # pip value) instead of a loud error.
    pair = pair.strip().upper().replace("-", "/")
    if pair not in PIP_SIZES:
        print(f"[Journal] WARNING: no pip config for pair {pair!r} — falling back to FX defaults")
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
    was_open = trade.result == "OPEN"

    # Normalize pair/direction the same way create_trade() does, so an edit
    # of "xau-usd" or "sell" lands on the same "XAU/USD" / "SELL" the pip
    # lookup and calculate_pnl() expect.
    if "pair" in update_data and update_data["pair"]:
        update_data["pair"] = update_data["pair"].strip().upper().replace("-", "/")
    if "direction" in update_data and update_data["direction"]:
        update_data["direction"] = update_data["direction"].strip().upper()

    # If close_price is being set, recalculate PnL correctly (authoritative
    # server-side calculation — overrides any pnl the client may have sent).
    close_price = update_data.get("close_price")
    if close_price and was_open:
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

        if not update_data.get("closed_at"):
            update_data["closed_at"] = datetime.now(timezone.utc)

    # Update account balance whenever this update resolves a previously-OPEN
    # trade — regardless of whether close_price was included. The old code
    # only credited the balance inside the close_price branch above, but the
    # frontend's inline "Close" button computes pnl/result client-side and
    # PATCHes {result, pnl, pnl_pips, closed_at} WITHOUT close_price, so that
    # path never touched the balance at all. Meanwhile delete_trade below
    # unconditionally *debits* trade.pnl for any non-OPEN trade being
    # deleted. Combined, every trade closed via that button and later
    # deleted silently drained the balance with no matching credit ever
    # having been applied — which is what caused the balance to drift far
    # below what Total PnL implies.
    new_result = update_data.get("result")
    if was_open and new_result and new_result != "OPEN":
        pnl_to_apply = update_data.get("pnl", trade.pnl or 0) or 0
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            old_balance = user.account_balance or 10000.0
            user.account_balance = round(old_balance + pnl_to_apply, 2)
            print(f"[Journal] Balance: {old_balance} + {pnl_to_apply} = {user.account_balance}")

    # Editing a mistake on a trade that was ALREADY closed before this
    # request (was_open is False) — e.g. the entry price was mistyped, the
    # wrong pair/direction was picked, or the lot size was wrong. If any of
    # the numbers that feed calculate_pnl() are changing, recompute pnl from
    # the corrected values and adjust the balance by the difference from
    # what was previously applied. Without this, correcting a typo would
    # silently leave the old (wrong) pnl baked into both the trade row and
    # the account balance.
    core_outcome_fields = {
        "pair", "direction", "entry_price", "lot_size",
        "close_price", "stop_loss", "take_profit",
    }
    if not was_open and trade.close_price is not None and core_outcome_fields & update_data.keys():
        new_pair = update_data.get("pair", trade.pair)
        new_direction = update_data.get("direction", trade.direction)
        new_entry = update_data.get("entry_price", trade.entry_price)
        new_lots = update_data.get("lot_size", trade.lot_size)
        new_close = update_data.get("close_price", trade.close_price)
        new_sl = update_data.get("stop_loss", trade.stop_loss)
        new_tp = update_data.get("take_profit", trade.take_profit)

        recomputed_pnl = calculate_pnl(
            pair=new_pair,
            direction=new_direction,
            entry=new_entry,
            close=new_close,
            lots=new_lots,
        )
        old_pnl = trade.pnl or 0
        pnl_diff = round(recomputed_pnl - old_pnl, 2)
        update_data["pnl"] = recomputed_pnl

        if "result" not in update_data:
            update_data["result"] = determine_result(
                direction=new_direction,
                entry=new_entry,
                close=new_close,
                stop_loss=new_sl,
                take_profit=new_tp,
            )

        if pnl_diff:
            user = db.query(User).filter(User.id == current_user.id).first()
            if user:
                old_balance = user.account_balance or 10000.0
                user.account_balance = round(old_balance + pnl_diff, 2)
                print(f"[Journal] Trade {trade_id} edited — pnl corrected {old_pnl} -> {recomputed_pnl}, balance adjusted by {pnl_diff}")

    for field, value in update_data.items():
        setattr(trade, field, value)

    db.commit()
    db.refresh(trade)

    return TradeResponse.model_validate(trade)


@router.delete("/clear-all")
def clear_all_trades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete every trade in the current user's journal. Does NOT touch
    account_balance — call /recalculate-balance afterwards (with whatever
    starting_balance you want) to reset it cleanly to a fresh number.

    NOTE: this route must stay registered BEFORE the dynamic
    DELETE /{trade_id} route below — FastAPI matches routes in the order
    they're defined, not by specificity, so if /{trade_id} came first it
    would swallow "/clear-all" as if "clear-all" were a trade_id and this
    endpoint would never be reached.
    """
    deleted_count = (
        db.query(Trade).filter(Trade.user_id == current_user.id).delete()
    )
    db.commit()

    return {"message": f"Deleted {deleted_count} trade(s).", "deleted_count": deleted_count}


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


@router.post("/recalculate-balance")
def recalculate_balance(
    starting_balance: float = Query(default=10000.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    One-time repair tool: recomputes account_balance from scratch as
    starting_balance + sum(pnl) across every closed trade currently in the
    journal, ignoring whatever drift accumulated from past balance-update
    bugs (see update_trade's close_price/pnl handling above). Safe to call
    any time you suspect the displayed balance no longer matches your
    trade history — it's idempotent.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    trades = db.query(Trade).filter(Trade.user_id == current_user.id).all()
    total_pnl = sum(t.pnl or 0 for t in trades if t.result in ["WIN", "LOSS", "BREAKEVEN"])

    old_balance = user.account_balance
    user.account_balance = round(starting_balance + total_pnl, 2)
    db.commit()
    db.refresh(user)

    print(f"[Journal] Balance recalculated: {old_balance} -> {user.account_balance} "
          f"(starting {starting_balance} + total_pnl {total_pnl})")

    return {
        "old_balance": old_balance,
        "new_balance": user.account_balance,
        "starting_balance": starting_balance,
        "total_pnl": round(total_pnl, 2),
    }
