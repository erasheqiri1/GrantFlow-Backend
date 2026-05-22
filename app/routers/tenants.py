from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.tenants import TenantListResponse
from app.services import tenants as tenant_service

router = APIRouter(prefix="/tenants", tags=["Tenants"])


def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm SUPER_ADMIN ka qasje në këtë endpoint")
    return current_user


@router.get("/stats", summary="Statistika të platformës (grants, aplikime, tenant)")
def platform_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return tenant_service.get_platform_stats(db)


@router.get("", response_model=TenantListResponse, summary="Lista e të gjitha organizatave")
def list_tenants(
    status: Optional[str] = Query(None, description="PENDING | ACTIVE | REJECTED"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return tenant_service.get_tenants(db, status)


@router.get("/stats", summary="Statistikat globale të platformës")
def platform_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return tenant_service.get_platform_stats(db)


@router.patch("/{tenant_id}/approve", summary="Aprovo organizatën")
def approve_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin),
):
    return tenant_service.approve_tenant(db, tenant_id, current_user["user_id"])


@router.patch("/{tenant_id}/reject", summary="Refuzo organizatën")
def reject_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin),
):
    return tenant_service.reject_tenant(db, tenant_id, current_user["user_id"])
