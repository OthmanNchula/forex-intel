from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.risk_calculator import calculate_full_risk
from app.services.alert_service import get_daily_risk, store_daily_risk
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/api/risk", tags=["Risk Management"])


class RiskCalculateRequest(BaseModel):
    pair: str
    entry_price: float
    stop_loss: float
    take_profit: float
    account_balance: float = None   # optional — uses user default if not provided
    risk_pct: float = None          # optional — uses user default if not provided


@router.post("/calculate")
def calculate_risk(
    payload: RiskCalculateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Calculate lot size, risk amount, potential profit, and R:R ratio.
    Uses user's saved balance and risk % if not provided in request.
    """
    balance = payload.account_balance or current_user.account_balance
    risk_pct = payload.risk_pct or current_user.risk_per_trade_pct

    if balance <= 0:
        raise HTTPException(status_code=400, detail="Account balance must be greater than 0.")
    if not (0.1 <= risk_pct <= 10.0):
        raise HTTPException(status_code=400, detail="Risk percentage must be between 0.1% and 10%.")

    result = calculate_full_risk(
        account_balance=balance,
        risk_pct=risk_pct,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        pair=payload.pair,
    )

    # Add daily exposure info
    daily_risk = get_daily_risk(str(current_user.id))
    daily_limit = balance * (current_user.max_daily_risk_pct / 100)
    remaining_daily = max(0, daily_limit - daily_risk)

    result["daily_risk_used"] = round(daily_risk, 2)
    result["daily_risk_limit"] = round(daily_limit, 2)
    result["daily_risk_remaining"] = round(remaining_daily, 2)

    if daily_risk + result["risk_amount"] > daily_limit:
        result["warnings"].append(
            f"⚠️ This trade would exceed your daily risk limit of "
            f"${daily_limit:.2f}. Consider reducing size or waiting tomorrow."
        )

    return result


@router.get("/daily-exposure")
def get_daily_exposure(current_user: User = Depends(get_current_user)):
    """Get today's total risk exposure for the current user."""
    daily_risk = get_daily_risk(str(current_user.id))
    balance = current_user.account_balance
    daily_limit = balance * (current_user.max_daily_risk_pct / 100)

    return {
        "daily_risk_used": round(daily_risk, 2),
        "daily_risk_limit": round(daily_limit, 2),
        "daily_risk_remaining": round(max(0, daily_limit - daily_risk), 2),
        "daily_risk_pct_used": round((daily_risk / daily_limit * 100) if daily_limit > 0 else 0, 1),
        "max_daily_risk_pct": current_user.max_daily_risk_pct,
        "account_balance": balance,
        "is_limit_reached": daily_risk >= daily_limit,
    }