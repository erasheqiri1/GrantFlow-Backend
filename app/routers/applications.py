import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.applications import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    AttachmentResponse, AIScoreResponse, CommissionerScoreRequest
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


def _require_applicant(user: dict):
    if user["role"] != "APPLICANT":
        raise HTTPException(status_code=403, detail="Vetëm APPLICANT mund ta kryejë këtë veprim")


def _require_reviewer(user: dict):
    """ORG_ADMIN dhe COMMISSIONER mund të shohin aplikimet."""
    if user["role"] not in ("ORG_ADMIN", "COMMISSIONER"):
        raise HTTPException(status_code=403, detail="Nuk ke leje")


def _require_commissioner(user: dict):
    """Vetëm COMMISSIONER mund të marrë vendime (aprovim/refuzim)."""
    if user["role"] != "COMMISSIONER":
        raise HTTPException(status_code=403, detail="Vetëm COMMISSIONER mund të marrë vendime")


def _require_org_admin(user: dict):
    """Vetëm ORG_ADMIN mund të caktojë komisionerë."""
    if user["role"] != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm ORG_ADMIN mund të kryejë këtë veprim")


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(
    data: ApplicationCreate,
    user=Depends(get_current_user),
):
    """Sistemi vetë e gjen tenant-in nga grant_id — aplikanti nuk duhet të dijë."""
    _require_applicant(user)
    # hap sesion publik për të gjetur schemën
    db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_grant(data.grant_id, db)
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.create_application(data, user, db)
    finally:
        db.close()


@router.get("/my", response_model=List[ApplicationResponse])
def get_my_applications(
    request: Request,
    user=Depends(get_current_user),
):
    _require_applicant(user)
    pub_db = SessionLocal()
    try:
        # ORG_ADMIN ka tenant_slug në token
        slug = getattr(request.state, "tenant_slug", None)
        if slug:
            schema_name = f"tenant_{slug.replace('-', '_')}"
            pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
            return app_service.get_my_applications(user, pub_db)

        # Aplikanti — kërko në të gjitha schemat
        schemas = app_service.find_schemas_for_user(user["user_id"], pub_db)
        all_apps = []
        for schema_name in schemas:
            db2 = SessionLocal()
            try:
                db2.execute(text(f'SET search_path TO "{schema_name}", public'))
                all_apps.extend(app_service.get_my_applications(user, db2))
            finally:
                db2.close()
        return all_apps
    finally:
        pub_db.close()


@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    user=Depends(get_current_user),
):
    _require_applicant(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.update_application(application_id, data, user, pub_db)
    finally:
        pub_db.close()


@router.post("/{application_id}/submit", response_model=ApplicationResponse)
def submit_application(
    application_id: str,
    user=Depends(get_current_user),
):
    _require_applicant(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.submit_application(application_id, user, pub_db)
    finally:
        pub_db.close()


@router.get("", response_model=List[ApplicationResponse])
def get_all_applications(
    grant_id:    Optional[str] = Query(None, description="Filtro sipas grant ID"),
    status:      Optional[str] = Query(None, description="SUBMITTED | UNDER_REVIEW | APPROVED | REJECTED"),
    assigned_to: Optional[str] = Query(None, description="UUID i komisionerit të caktuar"),
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_reviewer(user)
    return app_service.get_all_applications(db, grant_id, status, assigned_to)


@router.get("/{application_id}", response_model=ApplicationResponse)
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
    user=Depends(get_current_user),
):
    """Ngarko dokument mbështetës për aplikimin (PDF, JPG, PNG, DOC — max 5 MB)."""
    _require_applicant(user)

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
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pub_db.close()


class AssignRequest(BaseModel):
    commissioner_id: str

@router.patch("/{application_id}/assign", response_model=ApplicationResponse)
def assign_application(
    application_id: str,
    data: AssignRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    """ORG_ADMIN ricakton komisionerin për një aplikim."""
    _require_org_admin(user)
    return app_service.assign_application(application_id, data.commissioner_id, db)


@router.patch("/{application_id}/start-review", response_model=ApplicationResponse)
def start_review(
    application_id: str,
    user=Depends(get_current_user),
):
    _require_commissioner(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.start_review(application_id, user, pub_db)
    finally:
        pub_db.close()


@router.patch("/{application_id}/approve", response_model=ApplicationResponse)
def approve_application(
    application_id: str,
    user=Depends(get_current_user),
):
    _require_commissioner(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.approve_application(application_id, user, pub_db)
    finally:
        pub_db.close()


@router.patch("/{application_id}/reject", response_model=ApplicationResponse)
def reject_application(
    application_id: str,
    data: DecisionRequest = DecisionRequest(),
    user=Depends(get_current_user),
):
    _require_commissioner(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return app_service.reject_application(application_id, data.reason or "", user, pub_db)
    finally:
        pub_db.close()


@router.get("/{application_id}/attachments", response_model=List[AttachmentResponse])
def get_attachments(
    application_id: str,
    user=Depends(get_current_user),
):
    """Merr listën e dokumenteve të ngarkuara për aplikimin."""
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
    user=Depends(get_current_user),
):
    """Nis vlerësimin AI në background (Celery). Kthen 202 menjëherë."""
    _require_reviewer(user)
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
    user=Depends(get_current_user),
):
    """Merr rezultatin e AI për aplikimin (pollon derisa të jetë gati)."""
    _require_reviewer(user)
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
    user=Depends(get_current_user),
):
    """Komisioner ose ORG_ADMIN jep pikët (0-100). Rillogarit final_score."""
    _require_reviewer(user)
    pub_db = SessionLocal()
    try:
        schema_name = app_service.find_schema_for_application(application_id, pub_db)
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        return ai_scoring.set_commissioner_score(application_id, data.score, pub_db)
    finally:
        pub_db.close()