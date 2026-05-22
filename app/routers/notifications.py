from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.notifications import NotificationResponse
from app.services import notifications as notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return notification_service.get_notifications(current_user["user_id"], db)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return notification_service.mark_as_read(notification_id, current_user["user_id"], db)


@router.patch("/read-all")
def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return notification_service.mark_all_as_read(current_user["user_id"], db)
