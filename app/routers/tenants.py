from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.tenants import TenantListResponse, TenantResponse
from app.services.tenants import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get(
    "/public-stats",
    response_model=dict,
    summary="Statistika publike të platformës",
    description="Kthen statistika të përgjithshme (numri i organizatave, granteve) pa kërkuar autentikim.",
    responses={
        200: {"description": "Statistika publike"},
    },
)
def public_platform_stats(db: Session = Depends(get_db)):
    return TenantService(db).get_platform_stats()


@router.get(
    "/stats",
    summary="Statistika të platformës (me autentikim)",
    description="""
Kthen statistika të detajuara të platformës.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Statistika të detajuara"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
    },
)
def platform_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("tenants:read")),
):
    return TenantService(db).get_platform_stats()


@router.get(
    "",
    response_model=TenantListResponse,
    summary="Lista e organizatave",
    description="""
Kthen listën e paginuar të organizatave.

**Kërkon rolin:** `SUPER_ADMIN`

Filtro sipas statusit: `PENDING` (presin aprovim), `ACTIVE`, `REJECTED`.
""",
    responses={
        200: {"description": "Listë e paginuar e organizatave"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
    },
)
def list_tenants(
    status:  Optional[str] = Query(None, description="PENDING | ACTIVE | REJECTED"),
    sortBy:  str = Query("created_at", description="created_at | name"),
    sortDir: str = Query("desc",       description="asc | desc"),
    page:    int = Query(1,  ge=1),
    size:    int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("tenants:read")),
):
    return TenantService(db).get_tenants(status, sortBy, sortDir, page, size)


class TenantStatusUpdate(BaseModel):
    status: str


@router.patch(
    "/{tenant_id}/status",
    response_model=TenantResponse,
    summary="Ndrysho statusin e organizatës",
    description="""
Ndryshon statusin e një organizate.

**Kërkon rolin:** `SUPER_ADMIN`

Vlerat e lejuara për `status`:
- `APPROVED` — aprovo organizatën
- `REJECTED` — refuzo organizatën
""",
    responses={
        200: {"description": "Statusi i ndryshuar me sukses"},
        400: {"description": "Status i pavlefshëm"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Organizata nuk u gjet"},
    },
)
def update_tenant_status(
    tenant_id: str,
    data: TenantStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tenants:approve")),
):
    svc = TenantService(db)
    if data.status == "APPROVED":
        return svc.approve_tenant(tenant_id, current_user["user_id"])
    elif data.status == "REJECTED":
        return svc.reject_tenant(tenant_id, current_user["user_id"])
    raise HTTPException(status_code=400, detail="Status i pavlefshëm. Lejohet: APPROVED, REJECTED")
