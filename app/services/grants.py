import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.tenant.models import Grant, GrantStatus
from app.models.public.models import Tenant, TenantStatus
from app.schemas.grants import GrantCreate, GrantUpdate


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
    db.refresh(grant)
    return grant


def get_grants(db: Session, status: str = None) -> list:
    query = db.query(Grant)
    if status:
        query = query.filter(Grant.status == status)
    return query.order_by(Grant.created_at.desc()).all()


def get_all_published_grants(db: Session) -> list:
    """
    Për aplikantët pa tenant — merr të gjitha grantet PUBLISHED
    nga të gjitha organizatat aktive.
    """
    tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()
    all_grants = []

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
            continue  # schema nuk ekziston, kalo

        for row in rows:
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
            })

    return all_grants


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
    db.refresh(grant)
    return grant


def delete_grant(grant_id: str, db: Session) -> None:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të fshihen")
    db.delete(grant)
    db.commit()


def publish_grant(grant_id: str, db: Session) -> Grant:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Vetëm grantet DRAFT mund të publikohen")
    grant.status = GrantStatus.PUBLISHED
    db.commit()
    db.refresh(grant)
    return grant


def close_grant(grant_id: str, db: Session) -> Grant:
    grant = get_grant(grant_id, db)
    if grant.status != GrantStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Vetëm grantet PUBLISHED mund të mbyllen")
    grant.status = GrantStatus.CLOSED
    db.commit()
    db.refresh(grant)
    return grant
