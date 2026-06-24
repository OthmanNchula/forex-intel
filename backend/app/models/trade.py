import uuid
from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("signals.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Trade details
    pair = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)         # BUY or SELL
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    lot_size = Column(Float, nullable=False)
    risk_amount = Column(Float, nullable=False)            # USD at risk

    # Result
    result = Column(String(20), default="OPEN")           # WIN, LOSS, BREAKEVEN, OPEN
    pnl = Column(Float, nullable=True)                    # profit/loss in USD
    pnl_pips = Column(Float, nullable=True)               # profit/loss in pips

    # Timestamps
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Journal fields
    ai_reason = Column(Text, nullable=True)
    user_notes = Column(Text, nullable=True)
    screenshot_url = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User", backref="trades")
    signal = relationship("Signal", backref="trades")

    def __repr__(self):
        return f"<Trade {self.pair} {self.direction} {self.result}>"