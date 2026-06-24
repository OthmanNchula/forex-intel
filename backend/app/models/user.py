import uuid
from sqlalchemy import Column, String, Boolean, Float, ARRAY, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    account_balance = Column(Float, default=10000.0)       # demo balance in USD
    risk_per_trade_pct = Column(Float, default=1.0)        # default 1% risk
    max_daily_risk_pct = Column(Float, default=3.0)        # max 3% per day
    preferred_pairs = Column(
        ARRAY(String),
        default=["EUR/USD", "GBP/USD", "XAU/USD"],
    )
    timezone = Column(String(50), default="Africa/Dar_es_Salaam")
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=True)                # start in demo mode
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self):
        return f"<User {self.email}>"