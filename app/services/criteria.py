import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tenant.models import Criteria, ApplicationQuestion, Grant
from app.schemas.criteria import CriteriaCreate, CriteriaUpdate, QuestionCreate, QuestionUpdate


def _get_grant(grant_id: str, db: Session) -> Grant:
    try:
        gid = uuid.UUID(grant_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")
    grant = db.query(Grant).filter(Grant.id == gid).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant nuk u gjet")
    return grant


# ─────────────────────────────────────────
# Kriteret
# ─────────────────────────────────────────

def create_criteria(grant_id: str, data: CriteriaCreate, db: Session) -> Criteria:
    grant = _get_grant(grant_id, db)
    criteria = Criteria(
        grant_id=grant.id,
        name=data.name,
        weight=data.weight,
        min_value=data.min_value,
        is_required=data.is_required,
    )
    db.add(criteria)
    db.commit()
    return criteria


def get_criteria(grant_id: str, db: Session) -> list:
    grant = _get_grant(grant_id, db)
    return db.query(Criteria).filter(Criteria.grant_id == grant.id).all()


def update_criteria(grant_id: str, criteria_id: str, data: CriteriaUpdate, db: Session) -> Criteria:
    _get_grant(grant_id, db)
    try:
        cid = uuid.UUID(criteria_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="criteria_id i pavlefshëm")
    criteria = db.query(Criteria).filter(Criteria.id == cid).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Kriteri nuk u gjet")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(criteria, field, value)
    db.commit()
    return criteria


def delete_criteria(grant_id: str, criteria_id: str, db: Session) -> None:
    _get_grant(grant_id, db)
    try:
        cid = uuid.UUID(criteria_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="criteria_id i pavlefshëm")
    criteria = db.query(Criteria).filter(Criteria.id == cid).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Kriteri nuk u gjet")
    db.delete(criteria)
    db.commit()


# ─────────────────────────────────────────
# Pyetjet
# ─────────────────────────────────────────

def create_question(grant_id: str, data: QuestionCreate, db: Session) -> ApplicationQuestion:
    grant = _get_grant(grant_id, db)
    question = ApplicationQuestion(
        grant_id=grant.id,
        question_text=data.question_text,
        question_type=data.question_type,
        is_required=data.is_required,
        order_no=data.order_no,
    )
    db.add(question)
    db.commit()
    return question


def get_questions(grant_id: str, db: Session) -> list:
    grant = _get_grant(grant_id, db)
    return db.query(ApplicationQuestion).filter(
        ApplicationQuestion.grant_id == grant.id
    ).order_by(ApplicationQuestion.order_no).all()


def update_question(grant_id: str, question_id: str, data: QuestionUpdate, db: Session) -> ApplicationQuestion:
    _get_grant(grant_id, db)
    try:
        qid = uuid.UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id i pavlefshëm")
    question = db.query(ApplicationQuestion).filter(ApplicationQuestion.id == qid).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pyetja nuk u gjet")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    db.commit()
    return question


def delete_question(grant_id: str, question_id: str, db: Session) -> None:
    _get_grant(grant_id, db)
    try:
        qid = uuid.UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id i pavlefshëm")
    question = db.query(ApplicationQuestion).filter(ApplicationQuestion.id == qid).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pyetja nuk u gjet")
    db.delete(question)
    db.commit()