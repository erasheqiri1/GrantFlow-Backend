import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tenant.models import (
    Application, ApplicationAnswer, ApplicationStatus, Grant, GrantStatus
)
from app.models.public.models import Tenant, TenantStatus
from app.schemas.applications import ApplicationCreate, ApplicationUpdate


def find_schema_for_application(application_id: str, db: Session) -> str:
    """Kërkon në të gjitha schemat aktive për aplikimin me këtë ID."""
    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    for tenant in tenants:
        schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            row = db.execute(text(f"""
                SELECT id FROM "{schema_name}".applications WHERE id = :aid
            """), {"aid": application_id}).fetchone()
            if row:
                return schema_name
        except Exception:
            db.rollback()
            continue
    raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")


def find_schemas_for_user(user_id: str, db: Session) -> list:
    """Kthen listën e schemave ku ky user ka aplikime."""
    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    schemas = []
    for tenant in tenants:
        schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            row = db.execute(text(f"""
                SELECT 1 FROM "{schema_name}".applications WHERE user_id = :uid LIMIT 1
            """), {"uid": user_id}).fetchone()
            if row:
                schemas.append(schema_name)
        except Exception:
            db.rollback()
            continue
    return schemas


def find_schema_for_grant(grant_id: uuid.UUID, db: Session) -> str:
    """
    Kërkon në të gjitha schemat aktive për grant-in me këtë ID.
    Kthen schema_name (p.sh. 'tenant_elo') ose ngre 404.
    """
    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    for tenant in tenants:
        schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            row = db.execute(text(f"""
                SELECT id FROM "{schema_name}".grants
                WHERE id = :gid AND status = 'PUBLISHED'
            """), {"gid": str(grant_id)}).fetchone()
            if row:
                return schema_name
        except Exception:
            db.rollback()
            continue
    raise HTTPException(status_code=404, detail="Grant nuk u gjet ose nuk është PUBLISHED")


def create_application(data: ApplicationCreate, user: dict, db: Session) -> Application:
    # kontrollo nëse granti ekziston dhe është PUBLISHED
    try:
        gid = uuid.UUID(str(data.grant_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")

    grant = db.query(Grant).filter(Grant.id == gid).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant nuk u gjet")
    if grant.status != GrantStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Mund të aplikosh vetëm për grante PUBLISHED")

    # kontrollo nëse ka aplikuar tashmë
    existing = db.query(Application).filter(
        Application.grant_id == gid,
        Application.user_id == uuid.UUID(user["user_id"])
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ke aplikuar tashmë për këtë grant")

    application = Application(
        grant_id=gid,
        user_id=uuid.UUID(user["user_id"]),
        status=ApplicationStatus.DRAFT,
        motivation_letter=data.motivation_letter,
    )
    db.add(application)
    db.flush()

    # shto përgjigjet nëse ka
    for ans in (data.answers or []):
        answer = ApplicationAnswer(
            application_id=application.id,
            question_id=ans.question_id,
            answer_text=ans.answer_text,
        )
        db.add(answer)

    db.commit()
    db.refresh(application)
    return application


def get_my_applications(user: dict, db: Session) -> list:
    return db.query(Application).filter(
        Application.user_id == uuid.UUID(user["user_id"])
    ).order_by(Application.created_at.desc()).all()


def get_application(application_id: str, db: Session) -> Application:
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")
    app = db.query(Application).filter(Application.id == aid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
    return app


def update_application(application_id: str, data: ApplicationUpdate, user: dict, db: Session) -> Application:
    app = get_application(application_id, db)

    if str(app.user_id) != user["user_id"]:
        raise HTTPException(status_code=403, detail="Nuk ke leje të ndryshosh këtë aplikim")
    if app.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm aplikime DRAFT mund të ndryshohen")

    if data.motivation_letter is not None:
        app.motivation_letter = data.motivation_letter

    if data.answers is not None:
        # fshi përgjigjet e vjetra dhe shto të reja
        db.query(ApplicationAnswer).filter(
            ApplicationAnswer.application_id == app.id
        ).delete()
        for ans in data.answers:
            db.add(ApplicationAnswer(
                application_id=app.id,
                question_id=ans.question_id,
                answer_text=ans.answer_text,
            ))

    db.commit()
    db.refresh(app)
    return app


def submit_application(application_id: str, user: dict, db: Session) -> Application:
    app = get_application(application_id, db)

    if str(app.user_id) != user["user_id"]:
        raise HTTPException(status_code=403, detail="Nuk ke leje të dorëzosh këtë aplikim")
    if app.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm aplikime DRAFT mund të dorëzohen")

    app.status = ApplicationStatus.SUBMITTED
    app.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app)
    return app


def get_all_applications(db: Session, grant_id: str = None, status: str = None) -> list:
    query = db.query(Application)
    if grant_id:
        try:
            query = query.filter(Application.grant_id == uuid.UUID(grant_id))
        except ValueError:
            pass
    if status:
        query = query.filter(Application.status == status)
    return query.order_by(Application.created_at.desc()).all()