from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from app.core.database import SessionLocal
from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.applications import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse
)
from app.services import applications as app_service

router = APIRouter(prefix="/applications", tags=["Applications"])


def _require_applicant(user: dict):
    if user["role"] != "APPLICANT":
        raise HTTPException(status_code=403, detail="Vetëm APPLICANT mund ta kryejë këtë veprim")


def _require_reviewer(user: dict):
    if user["role"] not in ("ORG_ADMIN", "COMMISSIONER"):
        raise HTTPException(status_code=403, detail="Nuk ke leje")


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