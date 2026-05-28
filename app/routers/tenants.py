from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.tenants import TenantListResponse
from app.services import tenants as tenant_service

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get(
    "/public-stats",
    summary="Statistika publike të platformës",
    description="Kthen statistika të përgjithshme (numri i organizatave, granteve) pa kërkuar autentikim.",
    responses={
        200: {"description": "Statistika publike"},
    },
)
def public_platform_stats(db: Session = Depends(get_db)):
    return tenant_service.get_platform_stats(db)


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
    return tenant_service.get_platform_stats(db)


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
    return tenant_service.get_tenants(db, status, sortBy, sortDir, page, size)


@router.patch(
    "/{tenant_id}/approve",
    summary="Aprovo organizatën",
    description="""
Aprovon një organizatë në pritje dhe krijon schemën e saj në PostgreSQL.

**Kërkon rolin:** `SUPER_ADMIN`

Pas aprovimit, ORG_ADMIN i organizatës mund të kyçet dhe të menaxhojë grantet.
""",
    responses={
        200: {"description": "Organizatë e aprovuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Organizata nuk u gjet"},
    },
)
def approve_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tenants:approve")),
):
    return tenant_service.approve_tenant(db, tenant_id, current_user["user_id"])


@router.patch(
    "/{tenant_id}/reject",
    summary="Refuzo organizatën",
    description="""
Refuzon një organizatë në pritje.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Organizatë e refuzuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Organizata nuk u gjet"},
    },
)
def reject_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tenants:reject")),
):
    return tenant_service.reject_tenant(db, tenant_id, current_user["user_id"])
