from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.grants import GrantCreate, GrantUpdate, GrantResponse
from app.services import grants as grant_service

router = APIRouter(prefix="/grants", tags=["Grants"])


def _require_org_admin(user: dict):
    if user["role"] != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm ORG_ADMIN mund ta kryejë këtë veprim")


def get_db_for_slug(tenant_slug: str):
    """Hap sesion me search_path për slug-un e dhënë."""
    db = SessionLocal()
    try:
        schema_name = f"tenant_{tenant_slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        yield db
    finally:
        db.close()


@router.post("", response_model=GrantResponse, status_code=201)
def create_grant(
    data: GrantCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return grant_service.create_grant(data, user, db)


@router.get("", response_model=List[GrantResponse])
def get_grants(
    request: Request,
    status: Optional[str] = None,
    user=Depends(get_current_user),
):
    slug = getattr(request.state, "tenant_slug", None)

    if not slug:
        # APPLICANT pa tenant — shfaq të gjitha grantet PUBLISHED nga të gjitha orget
        from app.core.database import get_db
        db = SessionLocal()
        try:
            return grant_service.get_all_published_grants(db)
        finally:
            db.close()

    # ORG_ADMIN / COMMISSIONER — shfaq grantet e org-ut të tyre
    db = SessionLocal()
    try:
        schema_name = f"tenant_{slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return grant_service.get_grants(db, status)
    finally:
        db.close()


@router.get("/{grant_id}", response_model=GrantResponse)
def get_grant(
    request: Request,
    grant_id: str,
    tenant_slug: Optional[str] = None,
    user=Depends(get_current_user),
):
    slug = tenant_slug or getattr(request.state, "tenant_slug", None)
    if not slug:
        raise HTTPException(status_code=400, detail="Duhet tenant_slug.")
    db = SessionLocal()
    try:
        schema_name = f"tenant_{slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return grant_service.get_grant(grant_id, db)
    finally:
        db.close()


@router.patch("/{grant_id}", response_model=GrantResponse)
def update_grant(
    grant_id: str,
    data: GrantUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return grant_service.update_grant(grant_id, data, db)


@router.delete("/{grant_id}", status_code=204)
def delete_grant(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    grant_service.delete_grant(grant_id, db)


@router.patch("/{grant_id}/publish", response_model=GrantResponse)
def publish_grant(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return grant_service.publish_grant(grant_id, db)


@router.patch("/{grant_id}/close", response_model=GrantResponse)
def close_grant(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return grant_service.close_grant(grant_id, db)
