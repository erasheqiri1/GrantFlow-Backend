from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class ApplicationStatusEnum(str, Enum):
    DRAFT        = "DRAFT"
    SUBMITTED    = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED     = "APPROVED"
    REJECTED     = "REJECTED"


class AnswerCreate(BaseModel):
    question_id: UUID
    answer_text: Optional[str] = None


class AnswerResponse(BaseModel):
    id:          UUID
    question_id: UUID
    answer_text: Optional[str]
    created_at:  datetime

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    grant_id:         UUID
    motivation_letter: Optional[str] = None
    answers:          Optional[List[AnswerCreate]] = []


class ApplicationUpdate(BaseModel):
    motivation_letter: Optional[str] = None
    answers:          Optional[List[AnswerCreate]] = None


class ApplicationResponse(BaseModel):
    id:               UUID
    grant_id:         UUID
    grant_title:      Optional[str] = None
    user_id:          UUID
    status:           ApplicationStatusEnum
    motivation_letter: Optional[str]
    submitted_at:     Optional[datetime]
    decided_at:       Optional[datetime]
    decision_reason:  Optional[str]
    created_at:       datetime
    updated_at:       datetime
    answers:          Optional[List[AnswerResponse]] = []

    model_config = {"from_attributes": True}