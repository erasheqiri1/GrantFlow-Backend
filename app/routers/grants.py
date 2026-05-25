from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_tenant_db, require_permission
from app.schemas.grants import GrantCreate, GrantUpdate, GrantResponse
from app.services import grants as grant_service

router = APIRouter(prefix="/grants", tags=["Grants"])


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
    user=Depends(require_permission("grants:create")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.create_grant(data, user, db)


@router.get("", response_model=List[GrantResponse])
def get_grants(
    request: Request,
    status:         Optional[str] = Query(None, description="DRAFT | PUBLISHED | CLOSED"),
    title:          Optional[str] = Query(None, description="Kërko me fjalë kyçe në titull"),
    applicant_type: Optional[str] = Query(None, description="ANY | STUDENT | BUSINESS | ORGANIZATION | INDIVIDUAL"),
    deadline_from:  Optional[str] = Query(None, description="Grante me afat nga (YYYY-MM-DD) — tregon grante që skadojnë në ose pas kësaj date"),
    deadline_to:    Optional[str] = Query(None, description="Grante me afat deri (YYYY-MM-DD)"),
    budget_min:     Optional[float] = Query(None, description="Buxheti minimal"),
    budget_max:     Optional[float] = Query(None, description="Buxheti maksimal"),
    sort:           Optional[str] = Query(None, description="created_desc | deadline_asc | deadline_desc | budget_asc | budget_desc | title_asc"),
    user=Depends(require_permission("grants:read")),
):
    slug = getattr(request.state, "tenant_slug", None)

    if not slug:
        db = SessionLocal()
        try:
            return grant_service.get_all_published_grants(
                db, title, applicant_type, deadline_from, deadline_to,
                budget_min, budget_max, sort,
            )
        finally:
            db.close()

    db = SessionLocal()
    try:
        schema_name = f"tenant_{slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return grant_service.get_grants(
            db, status, title, applicant_type, deadline_from, deadline_to,
            budget_min, budget_max, sort,
        )
    finally:
        db.close()


@router.get("/{grant_id}", response_model=GrantResponse)
def get_grant(
    request: Request,
    grant_id: str,
    tenant_slug: Optional[str] = None,
    user=Depends(require_permission("grants:read")),
):
    slug = tenant_slug or getattr(request.state, "tenant_slug", None)
    db = SessionLocal()
    try:
        if slug:
            # ORG_ADMIN / COMMISSIONER — di schemën e tij
            schema_name = f"tenant_{slug.replace('-', '_')}"
        else:
            # APPLICANT — gjej schemën automatikisht nga grant_id
            from app.services.applications import find_schema_for_grant
            import uuid as _uuid
            try:
                gid = _uuid.UUID(grant_id)
            except ValueError:
                raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")
            schema_name = find_schema_for_grant(gid, db)

        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        result = grant_service.get_grant_detail(grant_id, db)
        # Shto tenant info nëse mungon slug-u (aplikant)
        if not slug:
            schema_slug = schema_name.replace("tenant_", "", 1)
            result["tenant_slug"] = schema_slug
        return result
    finally:
        db.close()


@router.patch("/{grant_id}", response_model=GrantResponse)
def update_grant(
    grant_id: str,
    data: GrantUpdate,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.update_grant(grant_id, data, db)


@router.delete("/{grant_id}", status_code=204)
def delete_grant(
    grant_id: str,
    user=Depends(require_permission("grants:delete")),
    db: Session = Depends(get_tenant_db),
):
    grant_service.delete_grant(grant_id, db)


@router.patch("/{grant_id}/publish", response_model=GrantResponse)
def publish_grant(
    grant_id: str,
    user=Depends(require_permission("grants:publish")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.publish_grant(grant_id, user, db)


@router.patch("/{grant_id}/close", response_model=GrantResponse)
def close_grant(
    grant_id: str,
    user=Depends(require_permission("grants:close")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.close_grant(grant_id, user, db)


# Finalizimi është automatik — thirret nga _check_auto_finalize në ai_scoring.py
# pas deadline + vlerësimit të plotë nga komisionerët.
