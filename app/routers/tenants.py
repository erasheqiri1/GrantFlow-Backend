from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.tenants import TenantListResponse
from app.services import tenants as tenant_service

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("/public-stats", summary="Statistika publike te platformes")
def public_platform_stats(db: Session = Depends(get_db)):
    return tenant_service.get_platform_stats(db)


@router.get("/stats", summary="Statistika të platformës (grants, aplikime, tenant)")
def platform_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("tenants:read")),
):
    return tenant_service.get_platform_stats(db)


@router.get("", response_model=TenantListResponse, summary="Lista e të gjitha organizatave")
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


@router.patch("/{tenant_id}/approve", summary="Aprovo organizatën")
def approve_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tenants:approve")),
):
    return tenant_service.approve_tenant(db, tenant_id, current_user["user_id"])


@router.patch("/{tenant_id}/reject", summary="Refuzo organizatën")
def reject_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tenants:reject")),
):
    return tenant_service.reject_tenant(db, tenant_id, current_user["user_id"])
