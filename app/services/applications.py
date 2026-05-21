import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tenant.models import (
    Application, ApplicationAnswer, ApplicationStatus,
    Grant, GrantStatus, CommissionerWorkload, Attachment
)
from app.models.public.models import Tenant, TenantStatus, UserRole, ApplicantProfile
from app.schemas.applications import ApplicationCreate, ApplicationUpdate
from app.services.audit import log_action


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

    # kontrollo nëse profili i aplikantit është i plotë
    applicant_profile = db.query(ApplicantProfile).filter(
        ApplicantProfile.user_id == uuid.UUID(user["user_id"])
    ).first()
    if not applicant_profile or not applicant_profile.applicant_type:
        raise HTTPException(status_code=400, detail="PROFILE_INCOMPLETE")

    # kontrollo nëse tipi i aplikantit përputhet me kërkesat e grantit
    if grant.applicant_type.value != "ANY":
        if applicant_profile.applicant_type.value != grant.applicant_type.value:
            raise HTTPException(
                status_code=403,
                detail=f"APPLICANT_TYPE_MISMATCH:{grant.applicant_type.value}"
            )

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
        status=ApplicationStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
        motivation_letter=data.motivation_letter,
    )
    db.add(application)
    db.flush()

    for ans in (data.answers or []):
        db.add(ApplicationAnswer(
            application_id=application.id,
            question_id=ans.question_id,
            answer_text=ans.answer_text,
        ))

    _auto_assign_commissioner(application, db)
    db.commit()
    log_action(db, user["user_id"], "SUBMIT_APPLICATION", "application", str(application.id),
               details={"grant_id": str(gid)})
    _enrich(application, db)
    return application


def _enrich_with_grant_title(app: Application, db: Session) -> None:
    """Shton grant_title si atribut dinamik te objekti Application."""
    try:
        grant = db.query(Grant).filter(Grant.id == app.grant_id).first()
        app.__dict__['grant_title'] = grant.title if grant else None
    except Exception:
        app.__dict__['grant_title'] = None


def _enrich_with_attachments(app: Application, db: Session) -> None:
    """Shton listën e attachments si atribut dinamik te objekti Application."""
    try:
        attachments = db.query(Attachment).filter(
            Attachment.application_id == app.id
        ).all()
        app.__dict__['attachments'] = attachments
    except Exception:
        app.__dict__['attachments'] = []


def _enrich(app: Application, db: Session) -> None:
    _enrich_with_grant_title(app, db)
    _enrich_with_attachments(app, db)


def get_my_applications(user: dict, db: Session) -> list:
    apps = db.query(Application).filter(
        Application.user_id == uuid.UUID(user["user_id"])
    ).order_by(Application.created_at.desc()).all()
    for app in apps:
        _enrich(app, db)
    return apps


def get_application(application_id: str, db: Session) -> Application:
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")
    app = db.query(Application).filter(Application.id == aid).first()
    if not app:
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
    _enrich(app, db)
    return app


def add_attachment(application_id: str, file_name: str, file_path: str,
                   file_type: str, size_bytes: int, db: Session) -> Attachment:
    """Shton një attachment te aplikimi."""
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")
    attachment = Attachment(
        application_id=aid,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        size_bytes=size_bytes,
    )
    db.add(attachment)
    db.commit()
    return attachment


def get_attachments(application_id: str, db: Session) -> list:
    """Kthen listën e attachments për një aplikim."""
    try:
        aid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")
    return db.query(Attachment).filter(Attachment.application_id == aid).all()


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
    return app


def _auto_assign_commissioner(app: Application, db: Session) -> None:
    """
    Gjen komisionerin me ngarkesën më të vogël dhe e cakton te aplikimi.
    Thirret automatikisht kur aplikimi submit-ohet.
    Nëse dështon (pa komisioner), nuk e ndal submit-in.
    """
    try:
        # Merr schema_name nga search_path aktive
        result = db.execute(text("SHOW search_path")).fetchone()
        schema_name = result[0].split(',')[0].strip().strip('"')
        tenant_slug = schema_name.replace('tenant_', '', 1)

        # Merr tenant
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if not tenant:
            return

        # Merr role_id të COMMISSIONER
        commissioner_role = db.execute(text(
            "SELECT id FROM public.roles WHERE name = 'COMMISSIONER'"
        )).fetchone()
        if not commissioner_role:
            return

        # Merr të gjithë komisionerët e këtij tenant
        rows = db.execute(text("""
            SELECT user_id FROM public.user_roles
            WHERE role_id = :role_id AND tenant_id = :tenant_id
        """), {"role_id": str(commissioner_role.id), "tenant_id": str(tenant.id)}).fetchall()

        if not rows:
            return

        commissioner_ids = [row.user_id for row in rows]

        # Gjej atë me assigned_count më të vogël
        workloads = db.query(CommissionerWorkload).filter(
            CommissionerWorkload.commissioner_id.in_(commissioner_ids)
        ).order_by(CommissionerWorkload.assigned_count.asc()).all()

        tracked_ids = {w.commissioner_id for w in workloads}
        untracked   = [cid for cid in commissioner_ids if cid not in tracked_ids]

        if untracked:
            # Ka komisioner pa asnjë caktim ende → zgjedh të parin
            chosen_id = untracked[0]
        elif workloads:
            chosen_id = workloads[0].commissioner_id
        else:
            return

        # Cakto komisionerin te aplikimi
        app.assigned_to = chosen_id

        # Përditëso ose krijo workload record
        workload = db.query(CommissionerWorkload).filter(
            CommissionerWorkload.commissioner_id == chosen_id
        ).first()
        if workload:
            workload.assigned_count += 1
        else:
            db.add(CommissionerWorkload(
                commissioner_id=chosen_id,
                assigned_count=1,
                completed_count=0,
            ))

    except Exception as e:
        # Mos e ndal submit-in nëse auto-assign dështon
        print(f"[auto-assign] dështoi: {e}")


def submit_application(application_id: str, user: dict, db: Session) -> Application:
    app = get_application(application_id, db)

    if str(app.user_id) != user["user_id"]:
        raise HTTPException(status_code=403, detail="Nuk ke leje të dorëzosh këtë aplikim")
    if app.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm aplikime DRAFT mund të dorëzohen")

    app.status = ApplicationStatus.SUBMITTED
    app.submitted_at = datetime.now(timezone.utc)

    # Auto-cakto komisionerin me ngarkesën më të vogël
    _auto_assign_commissioner(app, db)

    db.commit()
    log_action(db, user["user_id"], "SUBMIT_APPLICATION", "application", str(app.id))
    return app


def get_all_applications(
    db: Session,
    grant_id: str = None,
    status: str = None,
    assigned_to: str = None,
) -> list:
    query = db.query(Application).filter(
        Application.status != ApplicationStatus.DRAFT
    )
    if grant_id:
        try:
            query = query.filter(Application.grant_id == uuid.UUID(grant_id))
        except ValueError:
            pass
    if status:
        if status == "DRAFT":
            raise HTTPException(status_code=403, detail="Nuk mund të shihni aplikime DRAFT")
        query = query.filter(Application.status == status)
    if assigned_to:
        try:
            query = query.filter(Application.assigned_to == uuid.UUID(assigned_to))
        except ValueError:
            pass
    apps = query.order_by(Application.created_at.desc()).all()
    for app in apps:
        _enrich(app, db)
    return apps