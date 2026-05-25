import uuid
from datetime import datetime, time, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.models.tenant.models import Grant, GrantStatus, ApplicationQuestion, Application, ApplicationStatus, AIScore, Criteria
from app.models.public.models import Tenant, TenantStatus
from app.schemas.grants import GrantCreate, GrantUpdate
from app.services.audit import log_action


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


def _grant_amount(value):
    if value is None:
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def create_grant(data: GrantCreate, user: dict, db: Session) -> Grant:
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
    db.add(grant)
    db.commit()
    log_action(user["user_id"], "CREATE_GRANT", "grant", str(grant.id),
               tenant_id=user.get("tenant_id"), details={"title": data.title})
    return grant


def get_grants(
    db: Session,
    status: str = None,
    title: str = None,
    applicant_type: str = None,
    deadline_from: str = None,
    deadline_to: str = None,
    budget_min: float = None,
    budget_max: float = None,
    sort: str = None,
) -> list:
    query = db.query(Grant)
    if status:
        query = query.filter(Grant.status == status)
    if title:
        query = query.filter(Grant.title.ilike(f"%{title}%"))
    if applicant_type:
        query = query.filter(Grant.applicant_type == applicant_type)
    start_date = _parse_filter_date(deadline_from)
    end_date = _parse_filter_date(deadline_to, end_of_day=True)
    if start_date:
        query = query.filter(Grant.deadline >= start_date)
    if end_date:
        query = query.filter(Grant.deadline <= end_date)

    amount = func.coalesce(Grant.grant_value, Grant.budget, 0)
    if budget_min is not None:
        query = query.filter(amount >= budget_min)
    if budget_max is not None:
        query = query.filter(amount <= budget_max)

    if sort == "deadline_asc":
        query = query.order_by(Grant.deadline.asc().nullslast(), Grant.created_at.desc())
    elif sort == "deadline_desc":
        query = query.order_by(Grant.deadline.desc().nullslast(), Grant.created_at.desc())
    elif sort == "budget_asc":
        query = query.order_by(amount.asc(), Grant.created_at.desc())
    elif sort == "budget_desc":
        query = query.order_by(amount.desc(), Grant.created_at.desc())
    elif sort == "title_asc":
        query = query.order_by(Grant.title.asc(), Grant.created_at.desc())
    else:
        query = query.order_by(Grant.created_at.desc())

    grants = query.all()

    # Auto-mbyll grantet PUBLISHED me deadline të kaluar (FINALIZED nuk preket)
    now = datetime.now(timezone.utc)
    changed = False
    for g in grants:
        if (
            g.status == GrantStatus.PUBLISHED
            and g.deadline is not None
            and g.deadline < now
        ):
            g.status = GrantStatus.CLOSED
            changed = True
    if changed:
        db.commit()


    # Kthe dicts me questions: [] — shmanget gabimi i serializimit të ORM
    return [
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


def get_all_published_grants(
    db: Session,
    title: str = None,
    applicant_type: str = None,
    deadline_from: str = None,
    deadline_to: str = None,
    budget_min: float = None,
    budget_max: float = None,
    sort: str = None,
) -> list:
    """
    Për aplikantët pa tenant — merr të gjitha grantet PUBLISHED
    nga të gjitha organizatat aktive, me filtra opsionalë.
    Redis cache: TTL 60 sekonda për secilën kombinim filtrash.
    """
    from app.core.redis_client import cache_get, cache_set

    cache_key = (
        f"grants:public:{title or ''}:{applicant_type or ''}:{deadline_from or ''}:"
        f"{deadline_to or ''}:{budget_min or ''}:{budget_max or ''}:{sort or ''}"
    )
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[CACHE HIT]  {cache_key} — {len(cached)} grants nga Redis")
        return cached
    print(f"[CACHE MISS] {cache_key} — kërkon nga DB")

    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    all_grants = []
    start_date = _parse_filter_date(deadline_from)
    end_date = _parse_filter_date(deadline_to, end_of_day=True)

    for tenant in tenants:
        schema_name = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            rows = db.execute(text(f"""
                SELECT id, title, description, budget, currency, grant_value,
                       deadline, max_applicants, status, applicant_type,
                       ai_weight, created_at, updated_at
                FROM "{schema_name}".grants
                WHERE status = 'PUBLISHED'
                ORDER BY created_at DESC
            """)).fetchall()
        except Exception:
            db.rollback()
            continue

        for row in rows:
            if title and title.lower() not in (row.title or "").lower():
                continue
            if applicant_type and row.applicant_type != applicant_type:
                continue
            if start_date and (not row.deadline or row.deadline < start_date):
                continue
            if end_date and (not row.deadline or row.deadline > end_date):
                continue
            amount = _grant_amount(row.grant_value if row.grant_value is not None else row.budget)
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
            })

    if sort == "deadline_asc":
        all_grants.sort(key=lambda g: (g["deadline"] is None, g["deadline"] or datetime.max.replace(tzinfo=timezone.utc)))
    elif sort == "deadline_desc":
        all_grants.sort(key=lambda g: (g["deadline"] is None, g["deadline"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    elif sort == "budget_asc":
        all_grants.sort(key=lambda g: _grant_amount(g["grant_value"] if g["grant_value"] is not None else g["budget"]))
    elif sort == "budget_desc":
        all_grants.sort(key=lambda g: _grant_amount(g["grant_value"] if g["grant_value"] is not None else g["budget"]), reverse=True)
    elif sort == "title_asc":
        all_grants.sort(key=lambda g: (g["title"] or "").lower())

    cache_set(cache_key, all_grants, ttl=60)
    print(f"[CACHE SET]  {cache_key} — {len(all_grants)} grants u ruajtën (TTL 60s)")
    return all_grants


def get_grant_detail(grant_id: str, db: Session) -> dict:
    """
    Kthen grantin + pyetjet + kriteret.
    Përdoret nga GET /grants/{id} — aplikanti sheh çfarë duhet t'i përgjigjet dhe si vlerësohet.
    """
    grant = get_grant(grant_id, db)
    questions = (
        db.query(ApplicationQuestion)
        .filter(ApplicationQuestion.grant_id == grant.id)
        .order_by(ApplicationQuestion.order_no)
        .all()
    )
    criteria = (
        db.query(Criteria)
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


def get_grant(grant_id: str, db: Session) -> Grant:
    try:
        gid = uuid.UUID(grant_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="ID e pavlefshme")
    grant = db.query(Grant).filter(Grant.id == gid).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant nuk u gjet")
    return grant


def update_grant(grant_id: str, data: GrantUpdate, db: Session) -> Grant:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të ndryshohen")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(grant, field, value)
    db.commit()
    return grant


def delete_grant(grant_id: str, db: Session) -> None:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të fshihen")
    db.delete(grant)
    db.commit()


def publish_grant(grant_id: str, user: dict, db: Session) -> Grant:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të publikohen")

    # Nëse ka kritere, pesha totale duhet të jetë 100%
    criteria = db.query(Criteria).filter(Criteria.grant_id == grant.id).all()
    if criteria:
        total = round(sum(float(c.weight) for c in criteria) * 100)
        if total != 100:
            raise HTTPException(
                status_code=400,
                detail=f"Pesha totale e kritereve duhet të jetë 100% (tani: {total}%)"
            )

    grant.status = GrantStatus.PUBLISHED
    db.commit()
    log_action(user["user_id"], "PUBLISH_GRANT", "grant", str(grant.id),
               tenant_id=user.get("tenant_id"), details={"title": grant.title})
    # Invalido cache — grant i ri u bë publik
    from app.core.redis_client import cache_delete_pattern
    cache_delete_pattern("grants:public:*")
    return grant


def close_grant(grant_id: str, user: dict, db: Session) -> Grant:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Vetëm grantet PUBLISHED mund të mbyllen")
    grant.status = GrantStatus.CLOSED
    db.commit()
    log_action(user["user_id"], "CLOSE_GRANT", "grant", str(grant.id),
               tenant_id=user.get("tenant_id"), details={"title": grant.title})
    # Invalido cache — grant u mbyll
    from app.core.redis_client import cache_delete_pattern
    cache_delete_pattern("grants:public:*")
    return grant


def finalize_grant(grant_id: str, user: dict, db: Session) -> dict:
    """
    Finalizim AUTOMATIK — thirret nga _check_auto_finalize pas çdo vlerësimi komisioner.
    1. Merr të gjitha aplikimet SUBMITTED / UNDER_REVIEW të këtij granti
    2. Rendit: final_score DESC, submitted_at ASC (tiebreaker = kush dërgoi i pari)
    3. Top N (max_applicants) → APPROVED
    4. Të tjerët → REJECTED
    5. Shkruan rank_position tek ai_scores
    6. Grant → FINALIZED
    """
    grant = get_grant(grant_id, db)

    # Lejo finalizim edhe nëse granti është ende PUBLISHED por deadline ka kaluar
    now = datetime.now(timezone.utc)
    if grant.status == GrantStatus.PUBLISHED:
        if grant.deadline is None or grant.deadline >= now:
            raise HTTPException(status_code=400, detail="Granti është ende i hapur — prit të kalojë deadline")
        grant.status = GrantStatus.CLOSED
        db.flush()

    if grant.status not in (GrantStatus.CLOSED, GrantStatus.FINALIZED):
        raise HTTPException(status_code=400, detail="Vetëm grantet CLOSED mund të finalizohen")

    # Mos finalizo dy herë
    if grant.status == GrantStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Granti është finalizuar tashmë")

    max_n = grant.max_applicants  # None = pa limit

    # Merr aplikimet aktive
    active_statuses = [ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]
    applications = (
        db.query(Application)
        .filter(
            Application.grant_id == grant.id,
            Application.status.in_(active_statuses),
        )
        .all()
    )

    if not applications:
        raise HTTPException(status_code=400, detail="Nuk ka aplikime për të finalizuar")

    # Merr score për secilin
    scored = []
    for app in applications:
        score_row = db.query(AIScore).filter(AIScore.application_id == app.id).first()
        final = float(score_row.final_score) if score_row and score_row.final_score is not None else 0.0
        scored.append((app, score_row, final))

    # Rendit: final_score DESC, submitted_at ASC
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

        # Shkruaj rank_position
        if score_row:
            score_row.rank_position = rank
        elif rank <= (max_n or rank):
            # Krijo rresht minimal nëse nuk ka score
            new_score = AIScore(
                application_id=app.id,
                rank_position=rank,
                final_score=0.0,
                is_cached=False,
            )
            db.add(new_score)

    # Vendos statusin FINALIZED
    grant.status = GrantStatus.FINALIZED
    db.commit()
    log_action(user["user_id"], "FINALIZE_GRANT", "grant", str(grant.id),
               tenant_id=user.get("tenant_id"),
               details={"approved": approved_count, "rejected": rejected_count})

    # Dërgo email për çdo aplikant
    try:
        from app.tasks.email import send_application_result_email
        from sqlalchemy import text as _text
        for app, score_row, final in scored:
            row = db.execute(
                _text("SELECT email, first_name, last_name FROM public.users WHERE id = :uid"),
                {"uid": str(app.user_id)}
            ).fetchone()
            if row:
                full_name = f"{row.first_name} {row.last_name}".strip() or row.email
                approved  = app.status.value == "APPROVED"
                reason    = app.decision_reason or ""
                send_application_result_email.delay(
                    row.email, full_name, grant.title, approved, reason
                )
    except Exception:
        pass

    return {
        "status":   "finalized",
        "grant_id": grant_id,
        "approved": approved_count,
        "rejected": rejected_count,
        "total":    len(scored),
    }
