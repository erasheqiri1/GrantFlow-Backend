import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tenant.models import Criteria, ApplicationQuestion, Grant
from app.schemas.criteria import CriteriaCreate, CriteriaUpdate, QuestionCreate, QuestionUpdate


class CriteriaService:
    """Shërbimi për menaxhimin e kritereve dhe pyetjeve të granteve."""

    def __init__(self, db: Session):
        self.db = db

    def _get_grant(self, grant_id: str) -> Grant:
        try:
            gid = uuid.UUID(grant_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="grant_id i pavlefshëm")
        grant = self.db.query(Grant).filter(Grant.id == gid).first()
        if not grant:
            raise HTTPException(status_code=404, detail="Grant nuk u gjet")
        return grant

    # ── Kriteret ──────────────────────────────

    def create_criteria(self, grant_id: str, data: CriteriaCreate) -> Criteria:
        grant = self._get_grant(grant_id)
        criteria = Criteria(
            grant_id=grant.id,
            name=data.name,
            weight=data.weight,
            min_value=data.min_value,
            is_required=data.is_required,
        )
        self.db.add(criteria)
        self.db.commit()
        return criteria

    def get_criteria(self, grant_id: str) -> list:
        grant = self._get_grant(grant_id)
        return self.db.query(Criteria).filter(Criteria.grant_id == grant.id).all()

    def update_criteria(self, grant_id: str, criteria_id: str, data: CriteriaUpdate) -> Criteria:
        self._get_grant(grant_id)
        try:
            cid = uuid.UUID(criteria_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="criteria_id i pavlefshëm")
        criteria = self.db.query(Criteria).filter(Criteria.id == cid).first()
        if not criteria:
            raise HTTPException(status_code=404, detail="Kriteri nuk u gjet")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(criteria, field, value)
        self.db.commit()
        return criteria

    def delete_criteria(self, grant_id: str, criteria_id: str) -> None:
        self._get_grant(grant_id)
        try:
            cid = uuid.UUID(criteria_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="criteria_id i pavlefshëm")
        criteria = self.db.query(Criteria).filter(Criteria.id == cid).first()
        if not criteria:
            raise HTTPException(status_code=404, detail="Kriteri nuk u gjet")
        self.db.delete(criteria)
        self.db.commit()

    # ── Pyetjet ───────────────────────────────

    def create_question(self, grant_id: str, data: QuestionCreate) -> ApplicationQuestion:
        grant = self._get_grant(grant_id)
        question = ApplicationQuestion(
            grant_id=grant.id,
            question_text=data.question_text,
            question_type=data.question_type,
            is_required=data.is_required,
            order_no=data.order_no,
        )
        self.db.add(question)
        self.db.commit()
        return question

    def get_questions(self, grant_id: str) -> list:
        grant = self._get_grant(grant_id)
        return self.db.query(ApplicationQuestion).filter(
            ApplicationQuestion.grant_id == grant.id
        ).order_by(ApplicationQuestion.order_no).all()

    def update_question(self, grant_id: str, question_id: str, data: QuestionUpdate) -> ApplicationQuestion:
        self._get_grant(grant_id)
        try:
            qid = uuid.UUID(question_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="question_id i pavlefshëm")
        question = self.db.query(ApplicationQuestion).filter(ApplicationQuestion.id == qid).first()
        if not question:
            raise HTTPException(status_code=404, detail="Pyetja nuk u gjet")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(question, field, value)
        self.db.commit()
        return question

    def delete_question(self, grant_id: str, question_id: str) -> None:
        self._get_grant(grant_id)
        try:
            qid = uuid.UUID(question_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="question_id i pavlefshëm")
        question = self.db.query(ApplicationQuestion).filter(ApplicationQuestion.id == qid).first()
        if not question:
            raise HTTPException(status_code=404, detail="Pyetja nuk u gjet")
        self.db.delete(question)
        self.db.commit()
