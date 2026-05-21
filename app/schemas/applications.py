from pydantic import BaseModel, field_validator
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


class AttachmentResponse(BaseModel):
    id:          UUID
    file_name:   str
    file_path:   str
    file_type:   Optional[str] = None
    size_bytes:  Optional[int] = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    grant_id:              UUID
    motivation_letter:     Optional[str] = None
    answers:               Optional[List[AnswerCreate]] = []
    declaration_confirmed: bool = False

    @field_validator("declaration_confirmed")
    @classmethod
    def must_confirm_declaration(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Duhet të konfirmosh deklaratën para se të aplikosh")
        return v


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
    attachments:      Optional[List[AttachmentResponse]] = []

    model_config = {"from_attributes": True}