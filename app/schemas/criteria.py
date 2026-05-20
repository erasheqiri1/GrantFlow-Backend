from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID


class CriteriaCreate(BaseModel):
    name:        str
    weight:      float
    min_value:   Optional[float] = None
    is_required: Optional[bool]  = True

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v):
        if not (0 < v <= 1):
            raise ValueError("weight duhet të jetë mes 0 dhe 1")
        return v


class CriteriaUpdate(BaseModel):
    name:        Optional[str]   = None
    weight:      Optional[float] = None
    min_value:   Optional[float] = None
    is_required: Optional[bool]  = None


class CriteriaResponse(BaseModel):
    id:          UUID
    grant_id:    UUID
    name:        str
    weight:      float
    min_value:   Optional[float]
    is_required: bool

    model_config = {"from_attributes": True}


class QuestionCreate(BaseModel):
    question_text: str
    question_type: Optional[str] = "LONG_TEXT"
    is_required:   Optional[bool] = True
    order_no:      Optional[int]  = 1


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    is_required:   Optional[bool] = None
    order_no:      Optional[int]  = None


class QuestionResponse(BaseModel):
    id:            UUID
    grant_id:      UUID
    question_text: str
    question_type: str
    is_required:   bool
    order_no:      int

    model_config = {"from_attributes": True}
