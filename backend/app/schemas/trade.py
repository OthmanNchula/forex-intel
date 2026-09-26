from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class TradeCreate(BaseModel):
    pair: str
    direction: str                        # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_amount: float
    signal_id: Optional[uuid.UUID] = None
    ai_reason: Optional[str] = None
    user_notes: Optional[str] = None


class TradeUpdate(BaseModel):
    # Core trade fields — editable so a mistyped entry, wrong pair/direction,
    # etc. can be corrected after the fact instead of deleting and
    # re-adding the trade. See update_trade() in routers/journal.py for how
    # editing these on an already-closed trade recomputes pnl and adjusts
    # the account balance by the difference, so correcting a mistake never
    # leaves the balance out of sync with the corrected numbers.
    pair: Optional[str] = None
    direction: Optional[str] = None       # BUY or SELL
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    lot_size: Optional[float] = None
    risk_amount: Optional[float] = None

    close_price: Optional[float] = None
    result: Optional[str] = None          # WIN, LOSS, BREAKEVEN
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    closed_at: Optional[datetime] = None
    user_notes: Optional[str] = None
    screenshot_url: Optional[str] = None


class TradeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    pair: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_amount: float
    result: str
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    ai_reason: Optional[str] = None
    user_notes: Optional[str] = None
    screenshot_url: Optional[str] = None

    class Config:
        from_attributes = True


class TradeStats(BaseModel):
    total_trades: int
    open_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_rr: float