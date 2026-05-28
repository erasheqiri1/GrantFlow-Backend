from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_tenant_db, require_permission
from app.schemas.grants import GrantCreate, GrantUpdate, GrantResponse, PaginatedGrantResponse
from app.services import grants as grant_service

router = APIRouter(prefix="/grants", tags=["Grants"])


def get_db_for_slug(tenant_slug: str):
    """Hapet sesioni me search_path për slug te dhene."""
    db = SessionLocal()
    try:
        schema_name = f"tenant_{tenant_slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=GrantResponse,
    status_code=201,
    summary="Krijo grant të ri",
    description="""
Krijon një grant të ri me statusin **DRAFT**.

**Kërkon rolin:** `ORG_ADMIN`

Granti fillon si DRAFT dhe duhet publikuar manualisht me `PATCH /{grant_id}/publish`.
""",
    responses={
        201: {"description": "Grant i krijuar me sukses (status: DRAFT)"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        422: {"description": "Të dhëna të gabuara (fushat e detyrueshme mungojnë)"},
    },
)
def create_grant(
    data: GrantCreate,
    user=Depends(require_permission("grants:create")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.create_grant(data, user, db)


@router.get(
    "",
    response_model=PaginatedGrantResponse,
    summary="Merr listën e granteve",
    description="""
Kthen listën e paginuar të granteve.

**Sjellja sipas rolit:**
- `ORG_ADMIN` / `COMMISSIONER` → sheh grantet e organizatës (të gjitha statuset)
- `APPLICANT` → sheh vetëm grantet **PUBLISHED** nga të gjitha organizatat

**Filtrime të disponueshme:** status, titull, lloj aplikanti, deadline, buxhet
""",
    responses={
        200: {"description": "Listë e paginuar e granteve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
    },
)
def get_grants(
    request: Request,
    status:         Optional[str]   = Query(None, description="DRAFT | PUBLISHED | CLOSED"),
    title:          Optional[str]   = Query(None, description="Kërko me fjalë kyçe në titull"),
    applicant_type: Optional[str]   = Query(None, description="ANY | STUDENT | BUSINESS | ORGANIZATION | INDIVIDUAL"),
    deadline_from:  Optional[str]   = Query(None, description="Grante me afat nga (YYYY-MM-DD)"),
    deadline_to:    Optional[str]   = Query(None, description="Grante me afat deri (YYYY-MM-DD)"),
    budget_min:     Optional[float] = Query(None, description="Buxheti minimal"),
    budget_max:     Optional[float] = Query(None, description="Buxheti maksimal"),
    sortBy:         str = Query("created_at", description="created_at | deadline | budget | title"),
    sortDir:        str = Query("desc",       description="asc | desc"),
    page:           int = Query(1,  ge=1),
    size:           int = Query(10, ge=1, le=500),
    user=Depends(require_permission("grants:read")),
):
    slug = getattr(request.state, "tenant_slug", None)

    if not slug:
        db = SessionLocal()
        try:
            return grant_service.get_all_published_grants(
                db, title, applicant_type, deadline_from, deadline_to,
                budget_min, budget_max, sortBy, sortDir, page, size,
            )
        finally:
            db.close()

    db = SessionLocal()
    try:
        schema_name = f"tenant_{slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return grant_service.get_grants(
            db, status, title, applicant_type, deadline_from, deadline_to,
            budget_min, budget_max, sortBy, sortDir, page, size,
        )
    finally:
        db.close()


@router.get(
    "/{grant_id}",
    response_model=GrantResponse,
    summary="Detajet e një granti",
    description="""
Kthen të gjitha detajet e një granti sipas ID-së.

**Kërkon rolin:** Çdo user i autentikuar.

Sistemi gjen automatikisht organizatën nga `grant_id` — aplikanti nuk duhet të dijë tenant-in.
""",
    responses={
        200: {"description": "Detajet e grantit"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        404: {"description": "Granti nuk u gjet"},
        422: {"description": "grant_id i pavlefshëm (jo UUID)"},
    },
)
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
            #gjen schemën automatikisht nga grant_id
            from app.services.applications import find_schema_for_grant
            import uuid as _uuid
            try:
                gid = _uuid.UUID(grant_id)
            except ValueError:
                raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")
            schema_name = find_schema_for_grant(gid, db)

        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        result = grant_service.get_grant_detail(grant_id, db)
        # Shton tenant info nëse mungon slug
        if not slug:
            schema_slug = schema_name.replace("tenant_", "", 1)
            result["tenant_slug"] = schema_slug
        return result
    finally:
        db.close()


@router.patch(
    "/{grant_id}",
    response_model=GrantResponse,
    summary="Përditëso grant",
    description="""
Përditëson fushat e një granti ekzistues.

**Kërkon rolin:** `ORG_ADMIN`

Vetëm grantet me status **DRAFT** mund të modifikohen.
""",
    responses={
        200: {"description": "Grant i përditësuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
        422: {"description": "Të dhëna të gabuara"},
    },
)
def update_grant(
    grant_id: str,
    data: GrantUpdate,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.update_grant(grant_id, data, db)


@router.delete(
    "/{grant_id}",
    status_code=204,
    summary="Fshi grant",
    description="""
Fshin një grant nga sistemi.

**Kërkon rolin:** `ORG_ADMIN`

⚠️ Vetëm grantet me status **DRAFT** mund të fshihen.
""",
    responses={
        204: {"description": "Grant i fshirë me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def delete_grant(
    grant_id: str,
    user=Depends(require_permission("grants:delete")),
    db: Session = Depends(get_tenant_db),
):
    grant_service.delete_grant(grant_id, db)


@router.patch(
    "/{grant_id}/publish",
    response_model=GrantResponse,
    summary="Publiko grant",
    description="""
Ndryshon statusin e grantit nga **DRAFT** në **PUBLISHED**.

**Kërkon rolin:** `ORG_ADMIN`

Pas publikimit, granti bëhet i dukshëm për të gjithë aplikantët.
""",
    responses={
        200: {"description": "Grant i publikuar me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def publish_grant(
    grant_id: str,
    user=Depends(require_permission("grants:publish")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.publish_grant(grant_id, user, db)


@router.patch(
    "/{grant_id}/close",
    response_model=GrantResponse,
    summary="Mbyll grant",
    description="""
Mbyll një grant të publikuar — nuk pranohen më aplikime.

**Kërkon rolin:** `ORG_ADMIN`

Pas mbylljes, nis procesi i vlerësimit të aplikimeve.
""",
    responses={
        200: {"description": "Grant i mbyllur me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def close_grant(
    grant_id: str,
    user=Depends(require_permission("grants:close")),
    db: Session = Depends(get_tenant_db),
):
    return grant_service.close_grant(grant_id, user, db)


# Finalizimi është automatik — thirret nga _check_auto_finalize në ai_scoring.py
# pas deadline + vlerësimit të plotë nga komisionerët.
