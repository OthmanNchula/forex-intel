from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.alert import Alert
from app.services.alert_service import get_user_alerts
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


class AlertCreate(BaseModel):
    pair: str
    alert_type: str         # PRICE, RSI, EMA_CROSS, SL_HIT, TP_HIT
    condition_value: Optional[float] = None
    message: Optional[str] = None


@router.get("")
def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all alerts for current user."""
    db_alerts = db.query(Alert).filter(
        Alert.user_id == current_user.id,
    ).order_by(Alert.created_at.desc()).all()

    # Also get recent Redis notifications
    redis_notifications = get_user_alerts(str(current_user.id))

    return {
        "alerts": [
            {
                "id": str(a.id),
                "pair": a.pair,
                "alert_type": a.alert_type,
                "condition_value": a.condition_value,
                "message": a.message,
                "is_triggered": a.is_triggered,
                "triggered_at": a.triggered_at,
                "created_at": a.created_at,
            }
            for a in db_alerts
        ],
        "notifications": redis_notifications,
    }


@router.post("", status_code=201)
def create_alert(
    payload: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new price or indicator alert."""
    valid_types = ["PRICE", "RSI", "EMA_CROSS", "SL_HIT", "TP_HIT", "NEW_SIGNAL"]
    if payload.alert_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid alert type. Must be one of: {valid_types}"
        )

    alert = Alert(
        user_id=current_user.id,
        pair=payload.pair.upper().replace("-", "/"),
        alert_type=payload.alert_type,
        condition_value=payload.condition_value,
        message=payload.message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    return {
        "id": str(alert.id),
        "pair": alert.pair,
        "alert_type": alert.alert_type,
        "condition_value": alert.condition_value,
        "message": alert.message,
        "created_at": alert.created_at,
    }


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an alert."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id,
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    db.delete(alert)
    db.commit()

    return {"message": "Alert deleted successfully."}

@router.post("/test-telegram")
async def test_telegram(current_user: User = Depends(get_current_user)):
    """Send a test Telegram notification."""
    from app.services.telegram_service import send_test_notification
    success = await send_test_notification()
    if success:
        return {"message": "Test notification sent to Telegram successfully!"}
    return {"message": "Failed to send. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Railway variables."}

@router.post("/test-email")
async def test_email(current_user: User = Depends(get_current_user)):
    """Send a test email notification."""
    from app.services.email_service import send_test_email
    success = await send_test_email()
    if success:
        return {"message": "Test email sent to your Gmail successfully!"}
    return {"message": "Failed to send. Check RESEND_API_KEY and NOTIFICATION_EMAIL in Railway variables."}