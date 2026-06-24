import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

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

    pair = Column(String(20), nullable=False)
    alert_type = Column(String(30), nullable=False)       # PRICE, RSI, EMA_CROSS, SL_HIT, TP_HIT
    condition_value = Column(Float, nullable=True)        # price or threshold to trigger
    message = Column(Text, nullable=True)

    is_triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", backref="alerts")

    def __repr__(self):
        return f"<Alert {self.pair} {self.alert_type}>"