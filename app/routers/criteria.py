from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.auth import get_current_user, get_tenant_db
from app.schemas.criteria import (
    CriteriaCreate, CriteriaUpdate, CriteriaResponse,
    QuestionCreate, QuestionUpdate, QuestionResponse,
)
from app.services import criteria as criteria_service

router = APIRouter(prefix="/grants", tags=["Criteria & Questions"])


def _require_org_admin(user: dict):
    if user["role"] != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm ORG_ADMIN")


# ─────────────────────────────────────────
# CRITERIA
# ─────────────────────────────────────────

@router.post("/{grant_id}/criteria", response_model=List[CriteriaResponse], status_code=201)
def create_criteria(
    grant_id: str,
    data: List[CriteriaCreate],
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return [criteria_service.create_criteria(grant_id, item, db) for item in data]


@router.get("/{grant_id}/criteria", response_model=List[CriteriaResponse])
def get_criteria(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return criteria_service.get_criteria(grant_id, db)


@router.patch("/{grant_id}/criteria/{criteria_id}", response_model=CriteriaResponse)
def update_criteria(
    grant_id: str,
    criteria_id: str,
    data: CriteriaUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return criteria_service.update_criteria(grant_id, criteria_id, data, db)


@router.delete("/{grant_id}/criteria/{criteria_id}", status_code=204)
def delete_criteria(
    grant_id: str,
    criteria_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    criteria_service.delete_criteria(grant_id, criteria_id, db)


# ─────────────────────────────────────────
# QUESTIONS
# ─────────────────────────────────────────

@router.post("/{grant_id}/questions", response_model=List[QuestionResponse], status_code=201)
def create_question(
    grant_id: str,
    data: List[QuestionCreate],
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return [criteria_service.create_question(grant_id, item, db) for item in data]


@router.get("/{grant_id}/questions", response_model=List[QuestionResponse])
def get_questions(
    grant_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    return criteria_service.get_questions(grant_id, db)


@router.patch("/{grant_id}/questions/{question_id}", response_model=QuestionResponse)
def update_question(
    grant_id: str,
    question_id: str,
    data: QuestionUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    return criteria_service.update_question(grant_id, question_id, data, db)


@router.delete("/{grant_id}/questions/{question_id}", status_code=204)
def delete_question(
    grant_id: str,
    question_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    _require_org_admin(user)
    criteria_service.delete_question(grant_id, question_id, db)