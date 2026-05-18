import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.tenant.models import Grant, GrantStatus
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
