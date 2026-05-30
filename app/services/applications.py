import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tenant.models import (
    Application, ApplicationAnswer, ApplicationStatus,
    Grant, GrantStatus, CommissionerWorkload, Attachment, ApplicationQuestion
)
from app.models.public.models import Tenant, TenantStatus, UserRole, ApplicantProfile
from app.schemas.applications import ApplicationCreate, ApplicationUpdate
from app.services.audit import log_action


class ApplicationService:
    """Shërbimi për menaxhimin e aplikimeve."""

    def __init__(self, db: Session):
        self.db = db

    # ── Schema helpers ────────────────────────

    def find_schema_for_application(self, application_id: str) -> str:
        tenants = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
        for tenant in tenants:
            schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                row = self.db.execute(text(f"""
                    SELECT id FROM "{schema_name}".applications WHERE id = :aid
                """), {"aid": application_id}).fetchone()
                if row:
                    return schema_name
            except Exception:
                self.db.rollback()
                continue
        raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")

    def find_schemas_for_user(self, user_id: str) -> list:
        tenants = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
        schemas = []
        for tenant in tenants:
            schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                row = self.db.execute(text(f"""
                    SELECT 1 FROM "{schema_name}".applications WHERE user_id = :uid LIMIT 1
                """), {"uid": user_id}).fetchone()
                if row:
                    schemas.append(schema_name)
            except Exception:
                self.db.rollback()
                continue
        return schemas

    def find_schema_for_grant(self, grant_id: uuid.UUID) -> str:
        tenants = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
        for tenant in tenants:
            schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                row = self.db.execute(text(f"""
                    SELECT id FROM "{schema_name}".grants
                    WHERE id = :gid AND status::text IN ('PUBLISHED', 'CLOSED', 'FINALIZED')
                """), {"gid": str(grant_id)}).fetchone()
                if row:
                    return schema_name
            except Exception:
                self.db.rollback()
                continue
        raise HTTPException(status_code=404, detail="Grant nuk u gjet ose nuk është PUBLISHED")

    # ── Enrich helpers ────────────────────────

    def _enrich_with_grant_title(self, app: Application) -> None:
        try:
            grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
            app.__dict__['grant_title'] = grant.title if grant else None
        except Exception:
            app.__dict__['grant_title'] = None

    def _enrich_with_attachments(self, app: Application) -> None:
        try:
            attachments = self.db.query(Attachment).filter(
                Attachment.application_id == app.id
            ).all()
            app.__dict__['attachments'] = attachments
        except Exception:
            app.__dict__['attachments'] = []

    def _enrich_with_user_info(self, app: Application) -> None:
        try:
            row = self.db.execute(text(
                "SELECT email, first_name, last_name FROM public.users WHERE id = :uid"
            ), {"uid": str(app.user_id)}).fetchone()
            if row:
                app.__dict__['user_email'] = row.email
                app.__dict__['user_name']  = f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email
            else:
                app.__dict__['user_email'] = None
                app.__dict__['user_name']  = None
        except Exception:
            app.__dict__['user_email'] = None
            app.__dict__['user_name']  = None

    def _enrich_with_answers(self, app: Application) -> None:
        try:
            answers = (
                self.db.query(ApplicationAnswer)
                .filter(ApplicationAnswer.application_id == app.id)
                .all()
            )
            for ans in answers:
                q = self.db.query(ApplicationQuestion).filter(
                    ApplicationQuestion.id == ans.question_id
                ).first()
                ans.__dict__['question_text'] = q.question_text if q else None
            app.__dict__['answers'] = answers
        except Exception:
            app.__dict__['answers'] = []

    def _enrich(self, app: Application) -> None:
        self._enrich_with_grant_title(app)
        self._enrich_with_attachments(app)
        self._enrich_with_answers(app)
        self._enrich_with_user_info(app)

    # ── CRUD ──────────────────────────────────

    def create_application(self, data: ApplicationCreate, user: dict) -> Application:
        try:
            gid = uuid.UUID(str(data.grant_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")

        grant = self.db.query(Grant).filter(Grant.id == gid).first()
        if not grant:
            raise HTTPException(status_code=404, detail="Grant nuk u gjet")
        if grant.status != GrantStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="Mund të aplikosh vetëm për grante PUBLISHED")

        applicant_profile = self.db.query(ApplicantProfile).filter(
            ApplicantProfile.user_id == uuid.UUID(user["user_id"])
        ).first()
        if not applicant_profile or not applicant_profile.applicant_type:
            raise HTTPException(status_code=400, detail="PROFILE_INCOMPLETE")
        if not applicant_profile.personal_id:
            raise HTTPException(status_code=400, detail="PROFILE_MISSING_PERSONAL_ID")

        if grant.applicant_type.value != "ANY":
            if applicant_profile.applicant_type.value != grant.applicant_type.value:
                raise HTTPException(
                    status_code=403,
                    detail=f"APPLICANT_TYPE_MISMATCH:{grant.applicant_type.value}"
                )

        existing = self.db.query(Application).filter(
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
        self.db.add(application)
        self.db.flush()

        for ans in (data.answers or []):
            self.db.add(ApplicationAnswer(
                application_id=application.id,
                question_id=ans.question_id,
                answer_text=ans.answer_text,
            ))

        self._auto_assign_commissioner(application)
        self.db.commit()
        log_action(user["user_id"], "SUBMIT_APPLICATION", "application", str(application.id),
                   details={"grant_id": str(gid), "grant_title": grant.title})
        self._enrich(application)
        return application

    def get_application(self, application_id: str) -> Application:
        try:
            aid = uuid.UUID(application_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="ID e pavlefshme")
        app = self.db.query(Application).filter(Application.id == aid).first()
        if not app:
            raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
        self._enrich(app)
        return app

    def update_application(self, application_id: str, data: ApplicationUpdate, user: dict) -> Application:
        app = self.get_application(application_id)
        if str(app.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje të ndryshosh këtë aplikim")
        if app.status != ApplicationStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Vetëm aplikime DRAFT mund të ndryshohen")

        if data.motivation_letter is not None:
            app.motivation_letter = data.motivation_letter

        if data.answers is not None:
            self.db.query(ApplicationAnswer).filter(
                ApplicationAnswer.application_id == app.id
            ).delete()
            for ans in data.answers:
                self.db.add(ApplicationAnswer(
                    application_id=app.id,
                    question_id=ans.question_id,
                    answer_text=ans.answer_text,
                ))

        self.db.commit()
        return app

    def get_my_applications(
        self,
        user: dict,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 20,
        status: str = None,
    ) -> dict:
        col_map = {
            "created_at":   Application.created_at,
            "submitted_at": Application.submitted_at,
            "status":       Application.status,
        }
        col   = col_map.get(sort_by, Application.created_at)
        order = col.desc() if sort_dir == "desc" else col.asc()
        query = self.db.query(Application).filter(Application.user_id == uuid.UUID(user["user_id"]))
        if status:
            query = query.filter(Application.status == status)
        total = query.count()
        apps  = query.order_by(order).offset((page - 1) * size).limit(size).all()
        for app in apps:
            self._enrich(app)
        return {"total": total, "page": page, "size": size, "items": apps}

    def get_all_applications(
        self,
        grant_id: str = None,
        status: str = None,
        assigned_to: str = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 10,
    ) -> dict:
        query = self.db.query(Application).filter(
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
        col_map = {
            "created_at":   Application.created_at,
            "submitted_at": Application.submitted_at,
            "status":       Application.status,
        }
        col   = col_map.get(sort_by, Application.created_at)
        order = col.desc() if sort_dir == "desc" else col.asc()
        total = query.count()
        apps  = query.order_by(order).offset((page - 1) * size).limit(size).all()
        for app in apps:
            self._enrich(app)
        return {"total": total, "page": page, "size": size, "items": apps}

    def add_attachment(self, application_id: str, file_name: str, file_path: str,
                       file_type: str, size_bytes: int) -> Attachment:
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
        self.db.add(attachment)
        self.db.commit()
        return attachment

    def get_attachments(self, application_id: str) -> list:
        try:
            aid = uuid.UUID(application_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="ID e pavlefshme")
        return self.db.query(Attachment).filter(Attachment.application_id == aid).all()

    def assign_application(self, application_id: str, commissioner_id: str) -> Application:
        app = self.get_application(application_id)
        try:
            app.assigned_to = uuid.UUID(commissioner_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="commissioner_id i pavlefshëm")
        self.db.commit()
        self._enrich(app)
        return app

    def submit_application(self, application_id: str, user: dict) -> Application:
        app = self.get_application(application_id)
        if str(app.user_id) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Nuk ke leje të dorëzosh këtë aplikim")
        if app.status != ApplicationStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Vetëm aplikime DRAFT mund të dorëzohen")

        app.status       = ApplicationStatus.SUBMITTED
        app.submitted_at = datetime.now(timezone.utc)
        self._auto_assign_commissioner(app)
        self.db.commit()

        grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
        log_action(user["user_id"], "SUBMIT_APPLICATION", "application", str(app.id),
                   details={"grant_id": str(app.grant_id), "grant_title": grant.title if grant else None})
        return app

    def start_review(self, application_id: str, user: dict) -> Application:
        app = self.get_application(application_id)
        if app.status != ApplicationStatus.SUBMITTED:
            self._enrich(app)
            return app
        app.status = ApplicationStatus.UNDER_REVIEW
        self.db.commit()
        log_action(user["user_id"], "START_REVIEW", "application", str(app.id))
        self._enrich(app)
        return app

    def reset_to_submitted(self, application_id: str, user: dict) -> Application:
        app = self.get_application(application_id)
        if app.status != ApplicationStatus.UNDER_REVIEW:
            raise HTTPException(status_code=400, detail="Vetëm aplikimet 'Në shqyrtim' mund të kthehen")
        app.status = ApplicationStatus.SUBMITTED
        self.db.commit()
        log_action(user["user_id"], "RESET_TO_SUBMITTED", "application", str(app.id))
        self._enrich(app)
        return app

    def approve_application(self, application_id: str, user: dict) -> Application:
        app = self.get_application(application_id)
        if app.status not in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW):
            raise HTTPException(status_code=400, detail="Aplikimi nuk mund të aprovohet në këtë status")
        app.status     = ApplicationStatus.APPROVED
        app.decided_by = uuid.UUID(user["user_id"])
        app.decided_at = datetime.now(timezone.utc)
        grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
        self.db.commit()
        log_action(user["user_id"], "APPROVE_APPLICATION", "application", str(app.id),
                   details={"grant_title": grant.title if grant else None})
        try:
            from app.tasks.email import send_application_result_email
            row = self.db.execute(
                text("SELECT email, first_name, last_name FROM public.users WHERE id = :uid"),
                {"uid": str(app.user_id)}
            ).fetchone()
            if row:
                full_name = f"{row.first_name} {row.last_name}".strip() or row.email
                send_application_result_email.delay(row.email, full_name, grant.title if grant else "", True)
        except Exception:
            pass
        self._enrich(app)
        return app

    def reject_application(self, application_id: str, reason: str, user: dict) -> Application:
        app = self.get_application(application_id)
        if app.status not in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW):
            raise HTTPException(status_code=400, detail="Aplikimi nuk mund të refuzohet në këtë status")
        app.status          = ApplicationStatus.REJECTED
        app.decided_by      = uuid.UUID(user["user_id"])
        app.decided_at      = datetime.now(timezone.utc)
        app.decision_reason = reason or None
        grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
        self.db.commit()
        log_action(user["user_id"], "REJECT_APPLICATION", "application", str(app.id),
                   details={"grant_title": grant.title if grant else None, "reason": reason})
        try:
            from app.tasks.email import send_application_result_email
            row = self.db.execute(
                text("SELECT email, first_name, last_name FROM public.users WHERE id = :uid"),
                {"uid": str(app.user_id)}
            ).fetchone()
            if row:
                full_name = f"{row.first_name} {row.last_name}".strip() or row.email
                send_application_result_email.delay(row.email, full_name, grant.title if grant else "", False, reason or "")
        except Exception:
            pass
        self._enrich(app)
        return app

    # ── Private helpers ───────────────────────

    def _auto_assign_commissioner(self, app: Application) -> None:
        try:
            result      = self.db.execute(text("SHOW search_path")).fetchone()
            schema_name = result[0].split(',')[0].strip().strip('"')
            tenant_slug = schema_name.replace('tenant_', '', 1)

            tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
            if not tenant:
                return

            commissioner_role = self.db.execute(text(
                "SELECT id FROM public.roles WHERE name = 'COMMISSIONER'"
            )).fetchone()
            if not commissioner_role:
                return

            rows = self.db.execute(text("""
                SELECT user_id FROM public.user_roles
                WHERE role_id = :role_id AND tenant_id = :tenant_id
            """), {"role_id": str(commissioner_role.id), "tenant_id": str(tenant.id)}).fetchall()

            if not rows:
                return

            commissioner_ids = [row.user_id for row in rows]

            workloads = self.db.query(CommissionerWorkload).filter(
                CommissionerWorkload.commissioner_id.in_(commissioner_ids)
            ).order_by(
                CommissionerWorkload.assigned_count.asc(),
                CommissionerWorkload.updated_at.asc(),
            ).all()

            tracked_ids = {w.commissioner_id for w in workloads}
            untracked   = [cid for cid in commissioner_ids if cid not in tracked_ids]

            if untracked:
                chosen_id = untracked[0]
            elif workloads:
                chosen_id = workloads[0].commissioner_id
            else:
                return

            app.assigned_to = chosen_id

            workload = self.db.query(CommissionerWorkload).filter(
                CommissionerWorkload.commissioner_id == chosen_id
            ).first()
            if workload:
                workload.assigned_count += 1
            else:
                self.db.add(CommissionerWorkload(
                    commissioner_id=chosen_id,
                    assigned_count=1,
                    completed_count=0,
                ))

        except Exception as e:
            print(f"[auto-assign] dështoi: {e}")


# ── Module-level helpers për backward compat me routers ──────────────────────

def find_schema_for_application(application_id: str, db: Session) -> str:
    return ApplicationService(db).find_schema_for_application(application_id)


def find_schemas_for_user(user_id: str, db: Session) -> list:
    return ApplicationService(db).find_schemas_for_user(user_id)


def find_schema_for_grant(grant_id: uuid.UUID, db: Session) -> str:
    return ApplicationService(db).find_schema_for_grant(grant_id)
