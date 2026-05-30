from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.services.audit import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get(
    "",
    response_model=dict,
    summary="Audit logs të platformës",
    description="""
Kthen listën e paginuar të log-eve të veprimeve në platformë.

**Kërkon rolin:** `SUPER_ADMIN`

Regjistron çdo veprim të rëndësishëm: krijim granti, aprovim organizate, largim anëtari etj.

**Filtrime:** action, tenant_id, periudhë kohore
""",
    responses={
        200: {"description": "Listë e paginuar e audit log-eve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
    },
)
def get_audit_logs(
    action:    Optional[str]      = Query(None, description="p.sh. CREATE_GRANT, INVITE_USER"),
    tenant_id: Optional[str]      = Query(None, description="UUID i tenant-it"),
    from_date: Optional[datetime] = Query(None, description="Nga data (ISO 8601)"),
    to_date:   Optional[datetime] = Query(None, description="Deri ne date (ISO 8601)"),
    sortBy:    str                = Query("created_at", description="created_at | action | user_email"),
    sortDir:   str                = Query("desc",       description="asc | desc"),
    page:      int                = Query(1,  ge=1),
    size:      int                = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict     = Depends(require_permission("audit:read")),
):
    return AuditService(db).get_audit_logs(
        action=action,
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        sort_by=sortBy,
        sort_dir=sortDir,
        page=page,
        size=size,
    )
