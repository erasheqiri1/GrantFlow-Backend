import uuid
from datetime import datetime, time, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.models.tenant.models import Grant, GrantStatus, ApplicationQuestion, Application, ApplicationStatus, AIScore, Criteria
from app.models.public.models import Tenant, TenantStatus
from app.schemas.grants import GrantCreate, GrantUpdate
from app.services.audit import log_action


class GrantService:

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _parse_filter_date(value: str, end_of_day: bool = False):
        if not value:
            return None
        try:
            if len(value) == 10:
                parsed = datetime.fromisoformat(value)
                parsed = datetime.combine(parsed.date(), time.max if end_of_day else time.min)
            else:
                parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _grant_amount(value):
        if value is None:
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0

    def create_grant(self, data: GrantCreate, user: dict) -> Grant:
        grant = Grant(
            title=data.title,
            description=data.description,
            budget=data.budget,
            currency=data.currency or "EUR",
            grant_value=data.grant_value,
            deadline=data.deadline,
            max_applicants=data.max_applicants,
            applicant_type=data.applicant_type,
            ai_weight=data.ai_weight,
            status=GrantStatus.DRAFT,
            created_by=user["user_id"],
        )
        self.db.add(grant)
        self.db.commit()
        log_action(user["user_id"], "CREATE_GRANT", "grant", str(grant.id),
                   tenant_id=user.get("tenant_id"), details={"title": data.title})
        return grant

    def get_grants(
        self,
        status: str = None,
        title: str = None,
        applicant_type: str = None,
        deadline_from: str = None,
        deadline_to: str = None,
        budget_min: float = None,
        budget_max: float = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 10,
    ) -> dict:
        query = self.db.query(Grant)
        if status:
            query = query.filter(Grant.status == status)
        if title:
            _sv  = func.to_tsvector('simple',
                func.coalesce(Grant.title, '') + ' ' + func.coalesce(Grant.description, ''))
            _tsq = func.plainto_tsquery('simple', title)
            query = query.filter(_sv.op('@@')(_tsq))
        if applicant_type:
            query = query.filter(Grant.applicant_type == applicant_type)
        start_date = self._parse_filter_date(deadline_from)
        end_date   = self._parse_filter_date(deadline_to, end_of_day=True)
        if start_date:
            query = query.filter(Grant.deadline >= start_date)
        if end_date:
            query = query.filter(Grant.deadline <= end_date)

        amount = func.coalesce(Grant.grant_value, Grant.budget, 0)
        if budget_min is not None:
            query = query.filter(amount >= budget_min)
        if budget_max is not None:
            query = query.filter(amount <= budget_max)

        if title:
            _rank = func.ts_rank(
                func.to_tsvector('simple',
                    func.coalesce(Grant.title, '') + ' ' + func.coalesce(Grant.description, '')),
                func.plainto_tsquery('simple', title)
            )
            query = query.order_by(_rank.desc(), Grant.created_at.desc())
        else:
            asc_fn = lambda col: col.asc() if sort_dir == "asc" else col.desc()
            if sort_by == "deadline":
                query = query.order_by(asc_fn(Grant.deadline).nullslast(), Grant.created_at.desc())
            elif sort_by == "budget":
                query = query.order_by(asc_fn(amount), Grant.created_at.desc())
            elif sort_by == "title":
                query = query.order_by(asc_fn(Grant.title), Grant.created_at.desc())
            else:
                query = query.order_by(asc_fn(Grant.created_at))

        total  = query.count()
        offset = (page - 1) * size
        grants = query.offset(offset).limit(size).all()

        now = datetime.now(timezone.utc)
        changed = False
        for g in grants:
            if (g.status == GrantStatus.PUBLISHED
                    and g.deadline is not None
                    and g.deadline < now):
                g.status = GrantStatus.CLOSED
                changed = True
        if changed:
            self.db.commit()

        for g in grants:
            if g.status != GrantStatus.CLOSED:
                continue
            try:
                active_apps = self.db.query(Application).filter(
                    Application.grant_id == g.id,
                    Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW])
                ).all()
                if not active_apps:
                    continue
                all_scored = all(
                    self.db.query(AIScore).filter(
                        AIScore.application_id == a.id,
                        AIScore.commissioner_score.isnot(None)
                    ).first() is not None
                    for a in active_apps
                )
                if all_scored:
                    self.finalize_grant(str(g.id), {"user_id": str(active_apps[0].user_id), "tenant_id": None})
                    print(f"[auto-finalize] Grant '{g.title}' u finalizua.")
            except Exception as e:
                print(f"[auto-finalize] {g.id}: {e}")
                self.db.rollback()

        items = [
            {
                "id":             g.id,
                "title":          g.title,
                "description":    g.description,
                "budget":         float(g.budget)      if g.budget      else None,
                "currency":       g.currency,
                "grant_value":    float(g.grant_value) if g.grant_value else None,
                "deadline":       g.deadline,
                "max_applicants": g.max_applicants,
                "status":         g.status,
                "applicant_type": g.applicant_type,
                "ai_weight":      float(g.ai_weight),
                "created_at":     g.created_at,
                "questions":      [],
            }
            for g in grants
        ]
        return {"total": total, "page": page, "size": size, "items": items}

    def get_all_published_grants(
        self,
        title: str = None,
        applicant_type: str = None,
        deadline_from: str = None,
        deadline_to: str = None,
        budget_min: float = None,
        budget_max: float = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 10,
    ) -> dict:
        from app.core.redis_client import cache_get, cache_set

        cache_key = (
            f"grants:public:{title or ''}:{applicant_type or ''}:{deadline_from or ''}:"
            f"{deadline_to or ''}:{budget_min or ''}:{budget_max or ''}:{sort_by}:{sort_dir}"
        )
        cached = cache_get(cache_key)
        if cached is not None:
            print(f"[CACHE HIT]  {cache_key} — {len(cached)} grants nga Redis")
            total  = len(cached)
            offset = (page - 1) * size
            return {"total": total, "page": page, "size": size, "items": cached[offset:offset + size]}
        print(f"[CACHE MISS] {cache_key} — kërkon nga DB")

        tenants    = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
        all_grants = []
        start_date = self._parse_filter_date(deadline_from)
        end_date   = self._parse_filter_date(deadline_to, end_of_day=True)

        for tenant in tenants:
            schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                if title:
                    rows = self.db.execute(text(f"""
                        SELECT id, title, description, budget, currency, grant_value,
                               deadline, max_applicants, status, applicant_type,
                               ai_weight, created_at, updated_at,
                               ts_rank(
                                   to_tsvector('simple',
                                       coalesce(title,'') || ' ' ||
                                       coalesce(description,'') || ' ' ||
                                       :org_name
                                   ),
                                   plainto_tsquery('simple', :search)
                               ) AS rank
                        FROM "{schema_name}".grants
                        WHERE status = 'PUBLISHED'
                          AND to_tsvector('simple',
                                  coalesce(title,'') || ' ' ||
                                  coalesce(description,'') || ' ' ||
                                  :org_name
                              ) @@ plainto_tsquery('simple', :search)
                    """), {"search": title, "org_name": tenant.name}).fetchall()
                else:
                    rows = self.db.execute(text(f"""
                        SELECT id, title, description, budget, currency, grant_value,
                               deadline, max_applicants, status, applicant_type,
                               ai_weight, created_at, updated_at,
                               0 AS rank
                        FROM "{schema_name}".grants
                        WHERE status = 'PUBLISHED'
                        ORDER BY created_at DESC
                    """)).fetchall()
            except Exception:
                self.db.rollback()
                continue

            for row in rows:
                if applicant_type and row.applicant_type != applicant_type:
                    continue
                if start_date and (not row.deadline or row.deadline < start_date):
                    continue
                if end_date and (not row.deadline or row.deadline > end_date):
                    continue
                amount = self._grant_amount(row.grant_value if row.grant_value is not None else row.budget)
                if budget_min is not None and amount < budget_min:
                    continue
                if budget_max is not None and amount > budget_max:
                    continue

                all_grants.append({
                    "id":             row.id,
                    "title":          row.title,
                    "description":    row.description,
                    "budget":         float(row.budget) if row.budget else None,
                    "currency":       row.currency,
                    "grant_value":    float(row.grant_value) if row.grant_value else None,
                    "deadline":       row.deadline,
                    "max_applicants": row.max_applicants,
                    "status":         row.status,
                    "applicant_type": row.applicant_type,
                    "ai_weight":      float(row.ai_weight),
                    "created_at":     row.created_at,
                    "tenant_slug":    tenant.slug,
                    "org_name":       tenant.name,
                    "questions":      [],
                    "_rank":          float(row.rank),
                })

        reverse = sort_dir == "desc"
        if title:
            all_grants.sort(key=lambda g: g["_rank"], reverse=True)
        elif sort_by == "deadline":
            all_grants.sort(
                key=lambda g: (g["deadline"] is None, g["deadline"] or datetime.min.replace(tzinfo=timezone.utc)),
                reverse=reverse,
            )
        elif sort_by == "budget":
            all_grants.sort(
                key=lambda g: self._grant_amount(g["grant_value"] if g["grant_value"] is not None else g["budget"]),
                reverse=reverse,
            )
        elif sort_by == "title":
            all_grants.sort(key=lambda g: (g["title"] or "").lower(), reverse=reverse)
        else:
            all_grants.sort(key=lambda g: g["created_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=reverse)

        for g in all_grants:
            g.pop("_rank", None)

        cache_set(cache_key, all_grants, ttl=60)
        print(f"[CACHE SET]  {cache_key} — {len(all_grants)} grants u ruajtën (TTL 60s)")

        total  = len(all_grants)
        offset = (page - 1) * size
        return {"total": total, "page": page, "size": size, "items": all_grants[offset:offset + size]}

    def get_grant_detail(self, grant_id: str) -> dict:
        grant = self.get_grant(grant_id)
        questions = (
            self.db.query(ApplicationQuestion)
            .filter(ApplicationQuestion.grant_id == grant.id)
            .order_by(ApplicationQuestion.order_no)
            .all()
        )
        criteria = (
            self.db.query(Criteria)
            .filter(Criteria.grant_id == grant.id)
            .order_by(Criteria.name)
            .all()
        )
        return {
            "id":             grant.id,
            "title":          grant.title,
            "description":    grant.description,
            "budget":         float(grant.budget)      if grant.budget      else None,
            "currency":       grant.currency,
            "grant_value":    float(grant.grant_value) if grant.grant_value else None,
            "deadline":       grant.deadline,
            "max_applicants": grant.max_applicants,
            "status":         grant.status,
            "applicant_type": grant.applicant_type,
            "ai_weight":      float(grant.ai_weight),
            "created_at":     grant.created_at,
            "questions": [
                {
                    "id":            q.id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "is_required":   q.is_required,
                    "order_no":      q.order_no,
                }
                for q in questions
            ],
            "criteria": [
                {
                    "id":          str(c.id),
                    "name":        c.name,
                    "weight":      round(float(c.weight) * 100),
                    "is_required": c.is_required,
                }
                for c in criteria
            ],
        }

    def get_grant(self, grant_id: str) -> Grant:
        try:
            gid = uuid.UUID(grant_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="ID e pavlefshme")
        grant = self.db.query(Grant).filter(Grant.id == gid).first()
        if not grant:
            raise HTTPException(status_code=404, detail="Grant nuk u gjet")
        return grant

    def update_grant(self, grant_id: str, data: GrantUpdate) -> Grant:
        grant = self.get_grant(grant_id)
        if grant.status != GrantStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të ndryshohen")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(grant, field, value)
        self.db.commit()
        return grant

    def delete_grant(self, grant_id: str) -> None:
        grant = self.get_grant(grant_id)
        if grant.status != GrantStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të fshihen")
        self.db.delete(grant)
        self.db.commit()

    def publish_grant(self, grant_id: str, user: dict) -> Grant:
        grant = self.get_grant(grant_id)
        if grant.status != GrantStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të publikohen")

        criteria = self.db.query(Criteria).filter(Criteria.grant_id == grant.id).all()
        if criteria:
            total = round(sum(float(c.weight) for c in criteria) * 100)
            if total != 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pesha totale e kritereve duhet të jetë 100% (tani: {total}%)"
                )

        grant.status = GrantStatus.PUBLISHED
        self.db.commit()
        log_action(user["user_id"], "PUBLISH_GRANT", "grant", str(grant.id),
                   tenant_id=user.get("tenant_id"), details={"title": grant.title})
        from app.core.redis_client import cache_delete_pattern
        cache_delete_pattern("grants:public:*")
        return grant

    def close_grant(self, grant_id: str, user: dict) -> Grant:
        grant = self.get_grant(grant_id)
        if grant.status != GrantStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="Vetëm grantet PUBLISHED mund të mbyllen")
        grant.status = GrantStatus.CLOSED
        self.db.commit()
        log_action(user["user_id"], "CLOSE_GRANT", "grant", str(grant.id),
                   tenant_id=user.get("tenant_id"), details={"title": grant.title})
        from app.core.redis_client import cache_delete_pattern
        cache_delete_pattern("grants:public:*")
        return grant

    def finalize_grant(self, grant_id: str, user: dict) -> dict:
        grant = self.get_grant(grant_id)

        now = datetime.now(timezone.utc)
        if grant.status == GrantStatus.PUBLISHED:
            if grant.deadline is None or grant.deadline >= now:
                raise HTTPException(status_code=400, detail="Granti është ende i hapur — prit të kalojë deadline")
            grant.status = GrantStatus.CLOSED
            self.db.flush()

        if grant.status not in (GrantStatus.CLOSED, GrantStatus.FINALIZED):
            raise HTTPException(status_code=400, detail="Vetëm grantet CLOSED mund të finalizohen")

        if grant.status == GrantStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Granti është finalizuar tashmë")

        max_n = grant.max_applicants

        active_statuses = [ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]
        applications = (
            self.db.query(Application)
            .filter(
                Application.grant_id == grant.id,
                Application.status.in_(active_statuses),
            )
            .all()
        )

        if not applications:
            raise HTTPException(status_code=400, detail="Nuk ka aplikime për të finalizuar")

        scored = []
        for app in applications:
            score_row = self.db.query(AIScore).filter(AIScore.application_id == app.id).first()
            final = float(score_row.final_score) if score_row and score_row.final_score is not None else 0.0
            scored.append((app, score_row, final))

        scored.sort(key=lambda x: (-x[2], x[0].submitted_at or datetime.max.replace(tzinfo=timezone.utc)))

        now = datetime.now(timezone.utc)
        approved_count = 0
        rejected_count = 0

        for rank, (app, score_row, final) in enumerate(scored, start=1):
            if max_n is None or rank <= max_n:
                app.status     = ApplicationStatus.APPROVED
                app.decided_by = uuid.UUID(user["user_id"])
                app.decided_at = now
                approved_count += 1
            else:
                app.status     = ApplicationStatus.REJECTED
                app.decided_by = uuid.UUID(user["user_id"])
                app.decided_at = now
                rejected_count += 1

            if score_row:
                score_row.rank_position = rank
            elif rank <= (max_n or rank):
                new_score = AIScore(
                    application_id=app.id,
                    rank_position=rank,
                    final_score=0.0,
                    is_cached=False,
                )
                self.db.add(new_score)

        grant.status = GrantStatus.FINALIZED
        self.db.flush()

        try:
            from app.services.payments import PaymentService
            payment_svc = PaymentService(self.db)
            for app_obj, score_row, final in scored:
                if app_obj.status == ApplicationStatus.APPROVED:
                    payment_svc.create_payment_for_application(
                        application_id=app_obj.id,
                        amount=grant.grant_value or grant.budget,
                        currency=grant.currency or "EUR",
                    )
        except Exception as e:
            print(f"[finalize] Payment krijimi dështoi: {e}")

        self.db.commit()
        log_action(user["user_id"], "FINALIZE_GRANT", "grant", str(grant.id),
                   tenant_id=user.get("tenant_id"),
                   details={"approved": approved_count, "rejected": rejected_count})

        try:
            from app.tasks.email import send_application_result_email
            from sqlalchemy import text as _text

            for app_obj, score_row, final in scored:
                row = self.db.execute(
                    _text("SELECT email, first_name, last_name FROM public.users WHERE id = :uid"),
                    {"uid": str(app_obj.user_id)}
                ).fetchone()
                if not row:
                    continue
                full_name   = f"{row.first_name} {row.last_name}".strip() or row.email
                is_approved = app_obj.status == ApplicationStatus.APPROVED
                reason      = app_obj.decision_reason or ""
                try:
                    send_application_result_email.delay(
                        row.email, full_name, grant.title, is_approved, reason
                    )
                except Exception as email_err:
                    print(f"[finalize] Email dështoi për {row.email}: {email_err}")
        except Exception as e:
            print(f"[finalize] Email dërgimi dështoi: {e}")

        return {
            "status":   "finalized",
            "grant_id": grant_id,
            "approved": approved_count,
            "rejected": rejected_count,
            "total":    len(scored),
        }
