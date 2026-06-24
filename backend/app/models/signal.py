import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    pair = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, default="H1")
    direction = Column(String(10), nullable=False)         # BUY, SELL, NO_TRADE

    # Price levels
    current_price = Column(Float, nullable=False)
    entry_low = Column(Float, nullable=True)
    entry_high = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit_1 = Column(Float, nullable=True)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)

    # Risk metrics
    rr_ratio = Column(Float, nullable=True)
    confidence_score = Column(Integer, nullable=True)      # 0 to 100

    # AI output
    ai_explanation = Column(Text, nullable=True)
    risk_warning = Column(Text, nullable=True)

    # Indicator snapshot at signal time
    ema20 = Column(Float, nullable=True)
    ema50 = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Signal {self.pair} {self.direction} @ {self.current_price}>"