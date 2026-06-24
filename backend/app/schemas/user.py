from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import uuid


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    account_balance: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    max_daily_risk_pct: Optional[float] = None
    preferred_pairs: Optional[List[str]] = None
    timezone: Optional[str] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    account_balance: float
    risk_per_trade_pct: float
    max_daily_risk_pct: float
    preferred_pairs: List[str]
    timezone: str
    is_demo: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse