from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class SignalRequest(BaseModel):
    pair: str
    timeframe: str = "H1"


class SignalResponse(BaseModel):
    id: uuid.UUID
    pair: str
    timeframe: str
    direction: str
    current_price: float
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    rr_ratio: Optional[float] = None
    confidence_score: Optional[int] = None
    ai_explanation: Optional[str] = None
    risk_warning: Optional[str] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    rsi: Optional[float] = None
    macd_hist: Optional[float] = None
    atr: Optional[float] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True