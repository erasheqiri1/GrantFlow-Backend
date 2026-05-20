from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.services import audit as audit_service

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm SUPER_ADMIN ka qasje")
    return current_user


@router.get("")
def get_audit_logs(
    action:    Optional[str]      = Query(None, description="p.sh. CREATE_GRANT, INVITE_USER"),
    tenant_id: Optional[str]      = Query(None, description="UUID i tenant-it"),
    from_date: Optional[datetime] = Query(None, description="Nga data (ISO 8601)"),
    to_date:   Optional[datetime] = Query(None, description="Deri ne date (ISO 8601)"),
    limit:     int                = Query(100, ge=1, le=500),
    offset:    int                = Query(0,   ge=0),
    db: Session = Depends(get_db),
    _: dict     = Depends(require_super_admin),
):
    return audit_service.get_audit_logs(
        db=db,
        action=action,
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
