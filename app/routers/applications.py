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
from app.services.ai_scoring import AIScoreService
from app.services.applications import ApplicationService
from pydantic import BaseModel
from typing import Optional as Opt

class DecisionRequest(BaseModel):
    reason: Opt[str] = None

class AssignRequest(BaseModel):
    commissioner_id: str

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
        svc = ApplicationService(db)
        schema_name = svc.find_schema_for_grant(data.grant_id)
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return svc.create_application(data, user)
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
            return ApplicationService(pub_db).get_my_applications(user, sortBy, sortDir, page, size, status)

        schemas = ApplicationService(pub_db).find_schemas_for_user(user["user_id"])
        if not schemas:
            return {"total": 0, "page": page, "size": size, "items": []}

        total = 0
        all_items = []
        fetch_limit = page * size  # mjafton vetëm kaq për të llogaritur faqen e kërkuar

        for schema_name in schemas:
            db2 = SessionLocal()
            try:
                db2.execute(text(f'SET search_path TO "{schema_name}", public'))
                result = ApplicationService(db2).get_my_applications(user, sortBy, sortDir, 1, fetch_limit, status)
                total += result["total"]
                all_items.extend(result["items"])
            finally:
                db2.close()

        # Rirendit rezultatet e bashkuara nga skemat e ndryshme
        reverse = sortDir == "desc"
        attr_map = {"created_at": "created_at", "submitted_at": "submitted_at", "status": "status"}
        attr = attr_map.get(sortBy, "created_at")
        all_items.sort(key=lambda x: (getattr(x, attr) is None, getattr(x, attr) or ""), reverse=reverse)

        start = (page - 1) * size
        return {"total": total, "page": page, "size": size, "items": all_items[start: start + size]}
    finally:
        pub_db.close()


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Përditëso aplikimin",
    description="""
Përditëson të dhënat e një aplikimi ekzistues.

**Kërkon rolin:** `APPLICANT` (pronari i aplikimit)

Lejohet vetëm ndërsa aplikimi është në statusin **DRAFT**.
""",
    responses={
        200: {"description": "Aplikim i përditësuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    user=Depends(require_permission("applications:submit")),
):
    pub_db = SessionLocal()
    try:
        svc = ApplicationService(pub_db)
        schema_name = svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return svc.update_application(application_id, data, user)
    finally:
        pub_db.close()


class ApplicationStatusUpdate(BaseModel):
    status: str


@router.patch(
    "/{application_id}/status",
    response_model=ApplicationResponse,
    summary="Ndrysho statusin e aplikimit",
    description="""
Ndryshon statusin e aplikimit.

Vlerat e lejuara për `status`:
- `SUBMITTED` — dorëzon aplikimin (`APPLICANT`)
- `UNDER_REVIEW` — nis shqyrtimin (`ORG_ADMIN` / `COMMISSIONER`)
""",
    responses={
        200: {"description": "Statusi i ndryshuar me sukses"},
        400: {"description": "Status i pavlefshëm"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def update_application_status(
    application_id: str,
    data: ApplicationStatusUpdate,
    request: Request,
    user=Depends(get_current_user),
):
    role = getattr(request.state, "role", None)
    pub_db = SessionLocal()
    try:
        svc = ApplicationService(pub_db)
        schema_name = svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        if data.status == "SUBMITTED":
            if role != "APPLICANT":
                raise HTTPException(status_code=403, detail="Nuk ke leje — kërkohet APPLICANT")
            return svc.submit_application(application_id, user)
        elif data.status == "UNDER_REVIEW":
            if role not in ("ORG_ADMIN", "COMMISSIONER", "SUPER_ADMIN"):
                raise HTTPException(status_code=403, detail="Nuk ke leje — kërkohet ORG_ADMIN ose COMMISSIONER")
            return svc.start_review(application_id, user)
        raise HTTPException(status_code=400, detail="Status i pavlefshëm. Lejohet: SUBMITTED, UNDER_REVIEW")
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
    return ApplicationService(db).get_all_applications(grant_id, status, assigned_to, sortBy, sortDir, page, size)


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
        svc = ApplicationService(pub_db)
        schema_name = svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        application = svc.get_application(application_id)
        if user["role"] == "APPLICANT" and str(application.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje")
        return application
    finally:
        pub_db.close()


@router.post(
    "/{application_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
    summary="Ngarko dokument mbështetës",
    description="""
Ngarkon një dokument mbështetës për aplikimin (PDF, JPG, PNG, DOC — max 5 MB).

**Kërkon rolin:** `APPLICANT` (pronari i aplikimit)
""",
    responses={
        201: {"description": "Dokument i ngarkuar me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        413: {"description": "Skedari tejkalon limitin 5 MB"},
        415: {"description": "Lloji i skedarit nuk lejohet"},
    },
)
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
        svc = ApplicationService(pub_db)
        schema_name = svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Kontrollo që aplikimi i takon userit
        application = svc.get_application(application_id)
        if str(application.user_id) != user["user_id"]:
            os.remove(file_path)
            raise HTTPException(status_code=403, detail="Nuk ke leje")

        return svc.add_attachment(
            application_id=application_id,
            file_name=file.filename or unique_name,
            file_path=f"/uploads/attachments/{unique_name}",
            file_type=file.content_type,
            size_bytes=len(contents),
        )
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Gabim gjatë ngarkimit të skedarit")
    finally:
        pub_db.close()


@router.patch(
    "/{application_id}/commissioner",
    response_model=ApplicationResponse,
    summary="Cakto komisioner për aplikim",
    description="""
ORG_ADMIN cakton komisionerin përgjegjës për shqyrtimin e aplikimit.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        200: {"description": "Komisioner i caktuar me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Aplikimi ose komisioni nuk u gjet"},
    },
)
def assign_application(
    application_id: str,
    data: AssignRequest,
    user=Depends(require_permission("users:assign_role")),
    db: Session = Depends(get_tenant_db),
):
    """ORG_ADMIN cakton komisionerin për një aplikim."""
    return ApplicationService(db).assign_application(application_id, data.commissioner_id)


# Aprovimi/refuzimi bëhet automatikisht nga finalize_grant() pas deadline + vlerësimit komisioner.


@router.get(
    "/{application_id}/attachments",
    response_model=List[AttachmentResponse],
    summary="Dokumentet e aplikimit",
    description="""
Kthen listën e dokumenteve të ngarkuara për aplikimin.

**Kërkon:** User i autentikuar.

- `APPLICANT` → sheh vetëm dokumentet e aplikimeve të tij
- `ORG_ADMIN` / `COMMISSIONER` → sheh të gjitha dokumentet
""",
    responses={
        200: {"description": "Lista e dokumenteve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def get_attachments(
    application_id: str,
    user=Depends(get_current_user),
):
    """Funkaioni merr listën e dokumenteve të ngarkuara për aplikimin."""
    pub_db = SessionLocal()
    try:
        svc = ApplicationService(pub_db)
        schema_name = svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        application = svc.get_application(application_id)
        # Vetëm pronari ose reviewer mund të shohë dokumentet
        if user["role"] == "APPLICANT" and str(application.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje")
        return svc.get_attachments(application_id)
    finally:
        pub_db.close()


@router.post(
    "/{application_id}/score",
    status_code=202,
    response_model=dict,
    summary="Nis vlerësimin AI",
    description="""
Nis vlerësimin e aplikimit nga AI (OpenAI) si detyrë background (Celery).

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`

Kthen `202 Accepted` menjëherë. Pas ~5 sekondash, rezultati mund të merret me `GET /{application_id}/score`.

Nëse score ekziston tashmë, kthehet direkt pa ri-procesuar.
""",
    responses={
        202: {"description": "Vlerësimi u nis ose ekziston tashmë (cached)"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN ose COMMISSIONER"},
        404: {"description": "Aplikimi nuk u gjet"},
    },
)
def score_application(
    application_id: str,
    user=Depends(require_permission("applications:read_all")),
):
    """Nis vlerësimin AI në background (Celery). Kthen 202 menjëherë."""
    pub_db = SessionLocal()
    try:
        app_svc = ApplicationService(pub_db)
        schema_name = app_svc.find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))

        # Nëse ka cache — kthe direkt
        existing = AIScoreService(pub_db).get_score(application_id)
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


@router.get(
    "/{application_id}/score",
    response_model=AIScoreResponse,
    summary="Merr rezultatin e vlerësimit AI",
    description="""
Kthen rezultatin e vlerësimit AI për aplikimin.

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`

Nëse vlerësimi nuk ka përfunduar ende, kthen `404`. Pollon çdo 5 sekonda pas `POST /score`.
""",
    responses={
        200: {"description": "Rezultati i vlerësimit AI"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Vlerësimi nuk ekziston akoma — provo pas 5 sekondash"},
    },
)
def get_score(
    application_id: str,
    user=Depends(require_permission("applications:read_all")),
):
    """Merr rezultatin e AI për aplikimin (pollon derisa të jetë gati)."""
    pub_db = SessionLocal()
    try:
        schema_name = ApplicationService(pub_db).find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        score = AIScoreService(pub_db).get_score(application_id)
        if not score:
            raise HTTPException(status_code=404, detail="Nuk ka vlerësim AI akoma")
        return score
    finally:
        pub_db.close()


@router.patch(
    "/{application_id}/commissioner-score",
    response_model=AIScoreResponse,
    summary="Jep pikët e komisionerit",
    description="""
Komisioner ose ORG_ADMIN jep pikët manuale (0–100) për aplikimin.

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`

Pas regjistrimit të pikëve, `final_score` rillogaritet automatikisht si mesatare e AI score dhe commissioner score.
""",
    responses={
        200: {"description": "Pikët u regjistruan dhe final_score u rillogarit"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Aplikimi nuk u gjet"},
        422: {"description": "Pikët duhet të jenë ndërmjet 0 dhe 100"},
    },
)
def submit_commissioner_score(
    application_id: str,
    data: CommissionerScoreRequest,
    user=Depends(require_permission("applications:read_all")),
):
    """Komisioner ose ORG_ADMIN jep pikët (0-100). Rillogarit final_score."""
    pub_db = SessionLocal()
    try:
        schema_name = ApplicationService(pub_db).find_schema_for_application(application_id)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return AIScoreService(pub_db).set_commissioner_score(application_id, data.score)
    finally:
        pub_db.close()