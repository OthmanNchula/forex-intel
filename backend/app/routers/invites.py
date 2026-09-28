from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.email_service import send_invite_email
from app.services.alert_service import get_invite_count_today, increment_invite_count

router = APIRouter(prefix="/api/invites", tags=["Invites"])

# Simple per-user daily cap so a logged-in account can't be used to blast
# invite emails to strangers — this endpoint sends mail to an address the
# CALLER chooses, not the caller's own inbox, so it needs its own limit
# separate from the AI-call budgets in auto_signal_engine.py.
MAX_INVITES_PER_DAY = 10


class InviteRequest(BaseModel):
    email: EmailStr


@router.post("/send")
async def send_invite(
    payload: InviteRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Email an invite to try Forex Intel to an address the logged-in user
    chooses (e.g. a colleague). Rate-limited per user per day to prevent
    the endpoint being used to spam arbitrary addresses.
    """
    sent_today = get_invite_count_today(str(current_user.id))
    if sent_today >= MAX_INVITES_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"You've sent {MAX_INVITES_PER_DAY} invites today. Try again tomorrow.",
        )

    ok = await send_invite_email(payload.email, current_user.display_name or "A Forex Intel user")

    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Could not send the invite email. Please try again shortly.",
        )

    increment_invite_count(str(current_user.id))

    return {"sent": True, "to": payload.email}
