import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from app.core.file_validation import validate_magic_bytes
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_current_user, get_tenant_db, require_permission
from app.schemas.applications import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    AttachmentResponse, AIScoreResponse, CommissionerScoreRequest,
    PaginatedApplicationResponse,
)
from app.services import ai_scoring
from pydantic import BaseModel
from typing import Optional as Opt

class DecisionRequest(BaseModel):
    reason: Opt[str] = None

class AssignRequest(BaseModel):
    commissioner_id: str

from app.services import applications as app_service

UPLOAD_DIR = "uploads/attachments"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg", "image/jpg", "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

router = APIRouter(prefix="/applications", tags=["Applications"])




@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=201,
    summary="Krijo aplikim për grant",
    description="""
Krijon një aplikim të ri me statusin **DRAFT**.

**Kërkon rolin:** `APPLICANT`

Sistemi gjen automatikisht organizatën nga `grant_id` — aplikanti nuk duhet të dijë tenant-in.

Pas krijimit, aplikimi duhet dorëzuar me `POST /{application_id}/submit`.
""",
    responses={
        201: {"description": "Aplikim i krijuar (status: DRAFT)"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet APPLICANT"},
        404: {"description": "Granti nuk u gjet"},
        409: {"description": "Ke aplikuar tashmë për këtë grant"},
    },
)
def create_application(
    data: ApplicationCreate,
    user=Depends(require_permission("applications:submit")),
):
    """Sistemi vetë e gjen tenant-in nga grant_id — aplikanti nuk duhet të dijë."""
    # hap sesion publik për të gjetur schemën
    db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_grant(data.grant_id, db)
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.create_application(data, user, db)
    finally:
        db.close()


@router.get(
    "/my",
    response_model=PaginatedApplicationResponse,
    summary="Aplikimet e mia",
    description="""
Kthen listën e paginuar të aplikimeve të userit të kyçur.

**Kërkon rolin:** `APPLICANT`

Shfaq aplikimet nga të gjitha organizatat ku ka aplikuar useri.
""",
    responses={
        200: {"description": "Listë e paginuar e aplikimeve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet APPLICANT"},
    },
)
def get_my_applications(
    request: Request,
    status:  Optional[str] = Query(None, description="DRAFT | SUBMITTED | UNDER_REVIEW | APPROVED | REJECTED"),
    sortBy:  str = Query("created_at", description="created_at | submitted_at | status"),
    sortDir: str = Query("desc",       description="asc | desc"),
    page:    int = Query(1,   ge=1),
    size:    int = Query(20,  ge=1, le=200),
    user=Depends(require_permission("applications:read_own")),
):
    pub_db = SessionLocal()
    try:
        slug = getattr(request.state, "tenant_slug", None)
        if slug:
            schema_name = f"tenant_{slug.replace('-', '_')}"
            pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
            return app_service.get_my_applications(user, pub_db, sortBy, sortDir, page, size, status)

        schemas = app_service.find_schemas_for_user(user["user_id"], pub_db)
        all_apps = []
        for schema_name in schemas:
            db2 = SessionLocal()
            try:
                db2.execute(text(f'SET search_path TO "{schema_name}", public'))
                result = app_service.get_my_applications(user, db2, sortBy, sortDir, 1, 10_000, status)
                all_apps.extend(result["items"])
            finally:
                db2.close()
        total = len(all_apps)
        start = (page - 1) * size
        paged = all_apps[start: start + size]
        return {"total": total, "page": page, "size": size, "items": paged}
    finally:
        pub_db.close()


@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    user=Depends(require_permission("applications:submit")),
):
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.update_application(application_id, data, user, pub_db)
    finally:
        pub_db.close()


@router.post(
    "/{application_id}/submit",
    response_model=ApplicationResponse,
    summary="Dorëzo aplikimin",
    description="""
Ndryshon statusin e aplikimit nga **DRAFT** në **SUBMITTED**.

**Kërkon rolin:** `APPLICANT`

Pas dorëzimit, aplikimi nuk mund të modifikohet më.
""",
    responses={
        200: {"description": "Aplikim i dorëzuar (status: SUBMITTED)"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje ose aplikimi nuk është i juaji"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def submit_application(
    application_id: str,
    user=Depends(require_permission("applications:submit")),
):
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.submit_application(application_id, user, pub_db)
    finally:
        pub_db.close()


@router.get(
    "",
    response_model=PaginatedApplicationResponse,
    summary="Të gjitha aplikimet (ORG)",
    description="""
Kthen listën e paginuar të aplikimeve për organizatën aktuale.

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`

Mund të filtrohet sipas grant-it, statusit dhe komisionerit të caktuar.
""",
    responses={
        200: {"description": "Listë e paginuar e aplikimeve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN ose COMMISSIONER"},
    },
)
def get_all_applications(
    grant_id:    Optional[str] = Query(None, description="Filtro sipas grant ID"),
    status:      Optional[str] = Query(None, description="SUBMITTED | UNDER_REVIEW | APPROVED | REJECTED"),
    assigned_to: Optional[str] = Query(None, description="UUID i komisionerit të caktuar"),
    sortBy:      str = Query("created_at", description="created_at | submitted_at | status"),
    sortDir:     str = Query("desc",       description="asc | desc"),
    page:        int = Query(1,  ge=1),
    size:        int = Query(10, ge=1, le=500),
    user=Depends(require_permission("applications:read_all")),
    db: Session = Depends(get_tenant_db),
):
    return app_service.get_all_applications(db, grant_id, status, assigned_to, sortBy, sortDir, page, size)


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Detajet e një aplikimi",
    description="""
Kthen detajet e plotë të një aplikimi.

**Kërkon:** User i autentikuar.

- `APPLICANT` → sheh vetëm aplikimet e tij
- `ORG_ADMIN` / `COMMISSIONER` → sheh të gjitha aplikimet e organizatës
""",
    responses={
        200: {"description": "Detajet e aplikimit"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — aplikimi i takon dikujt tjetër"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def get_application(
    application_id: str,
    user=Depends(get_current_user),
):
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        application = app_service.get_application(application_id, pub_db)
        if user["role"] == "APPLICANT" and str(application.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje")
        return application
    finally:
        pub_db.close()


@router.post("/{application_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    application_id: str,
    file: UploadFile = File(...),
    user=Depends(require_permission("applications:submit")),
):
    """Ngarko dokument mbështetës për aplikimin (PDF, JPG, PNG, DOC — max 5 MB)."""

    # Kontrollo llojin e skedarit
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Lloji i skedarit nuk lejohet. Lejohen: PDF, JPG, PNG, DOC, DOCX"
        )

    # Lexo skedarin dhe kontrollo madhësinë
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Skedari është shumë i madh. Maksimumi është 5 MB."
        )

    # Kontrollo magic bytes — parandalon fshehjen e skedarëve të rrezikshëm
    validate_magic_bytes(contents, file.content_type)

    # Ruaj skedarin në disk me emër unik
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "doc")[1] or ".bin"
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    # Gjej schemën dhe ruaj në DB
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Kontrollo që aplikimi i takon userit
        application = app_service.get_application(application_id, pub_db)
        if str(application.user_id) != user["user_id"]:
            os.remove(file_path)
            raise HTTPException(status_code=403, detail="Nuk ke leje")

        return app_service.add_attachment(
            application_id=application_id,
            file_name=file.filename or unique_name,
            file_path=f"/uploads/attachments/{unique_name}",
            file_type=file.content_type,
            size_bytes=len(contents),
            db=pub_db,
        )
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Gabim gjatë ngarkimit të skedarit")
    finally:
        pub_db.close()


@router.patch("/{application_id}/assign", response_model=ApplicationResponse)
def assign_application(
    application_id: str,
    data: AssignRequest,
    user=Depends(require_permission("users:assign_role")),
    db: Session = Depends(get_tenant_db),
):
    """ORG_ADMIN ricakton komisionerin për një aplikim."""
    return app_service.assign_application(application_id, data.commissioner_id, db)


@router.patch("/{application_id}/start-review", response_model=ApplicationResponse)
def start_review(
    application_id: str,
    user=Depends(require_permission("applications:read_all")),
):
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.start_review(application_id, user, pub_db)
    finally:
        pub_db.close()


# Aprovimi/refuzimi bëhet automatikisht nga finalize_grant() pas deadline + vlerësimit komisioner.


@router.get("/{application_id}/attachments", response_model=List[AttachmentResponse])
def get_attachments(
    application_id: str,
    user=Depends(get_current_user),
):
    """Funkaioni merr listën e dokumenteve të ngarkuara për aplikimin."""
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        application = app_service.get_application(application_id, pub_db)
        # Vetëm pronari ose reviewer mund të shohë dokumentet
        if user["role"] == "APPLICANT" and str(application.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje")
        return app_service.get_attachments(application_id, pub_db)
    finally:
        pub_db.close()


@router.post("/{application_id}/score", status_code=202)
def score_application(
    application_id: str,
    user=Depends(require_permission("applications:read_all")),
):
    """Nis vlerësimin AI në background (Celery). Kthen 202 menjëherë."""
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Nëse ka cache — kthe direkt
        existing = ai_scoring.get_score(application_id, pub_db)
        if existing and existing.ai_score is not None:
            existing.is_cached = True
            pub_db.commit()
            return {"status": "cached", "message": "Score ekziston tashmë"}

        # Queue Celery task — AI punon në background
        from app.tasks.ai_tasks import score_application_task
        score_application_task.delay(application_id, schema_name)
        return {"status": "processing", "message": "Vlerësimi AI u nis. Rifresko pas 5 sekondash."}
    finally:
        pub_db.close()


@router.get("/{application_id}/score", response_model=AIScoreResponse)
def get_score(
    application_id: str,
    user=Depends(require_permission("applications:read_all")),
):
    """Merr rezultatin e AI për aplikimin (pollon derisa të jetë gati)."""
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        score = ai_scoring.get_score(application_id, pub_db)
        if not score:
            raise HTTPException(status_code=404, detail="Nuk ka vlerësim AI akoma")
        return score
    finally:
        pub_db.close()


@router.patch("/{application_id}/commissioner-score", response_model=AIScoreResponse)
def submit_commissioner_score(
    application_id: str,
    data: CommissionerScoreRequest,
    user=Depends(require_permission("applications:read_all")),
):
    """Komisioner ose ORG_ADMIN jep pikët (0-100). Rillogarit final_score."""
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return ai_scoring.set_commissioner_score(application_id, data.score, pub_db)
    finally:
        pub_db.close()