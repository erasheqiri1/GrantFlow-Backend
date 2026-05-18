from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.grants import GrantCreate, GrantUpdate, GrantResponse
from app.services import grants as grant_service

router = APIRouter(prefix="/grants", tags=["Grants"])


def _require_org_admin(user: dict):
    if user["role"] != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm ORG_ADMIN mund ta kryejë këtë veprim")


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
    status: Optional[str] = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.get_grants(db, status)


@router.get("/{grant_id}", response_model=GrantResponse)
def get_grant(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.get_grant(grant_id, db)


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
