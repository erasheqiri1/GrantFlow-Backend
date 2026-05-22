import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tenant.models import Notification


def get_notifications(user_id: str, db: Session) -> list:
    return (
        db.query(Notification)
        .filter(Notification.user_id == uuid.UUID(user_id))
        .order_by(Notification.created_at.desc())
        .all()
    )


def mark_as_read(notification_id: str, user_id: str, db: Session) -> Notification:
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")

    notification = db.query(Notification).filter(
        Notification.id == nid,
        Notification.user_id == uuid.UUID(user_id),
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Njoftimi nuk u gjet")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_as_read(user_id: str, db: Session) -> dict:
    db.query(Notification).filter(
        Notification.user_id == uuid.UUID(user_id),
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "Të gjitha njoftimet u shënuan si të lexuara"}
