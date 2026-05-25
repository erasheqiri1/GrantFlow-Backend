from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID


class GrantStatusEnum(str, Enum):
    DRAFT     = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED    = "CLOSED"
    FINALIZED = "FINALIZED"


class ApplicantTypeEnum(str, Enum):
    ANY          = "ANY"
    STUDENT      = "STUDENT"
    BUSINESS     = "BUSINESS"
    ORGANIZATION = "ORGANIZATION"
    INDIVIDUAL   = "INDIVIDUAL"


class GrantCreate(BaseModel):
    title:          str
    description:    Optional[str]   = None
    budget:         Optional[float] = None
    currency:       Optional[str]   = "EUR"
    grant_value:    Optional[float] = None
    deadline:       Optional[datetime] = None
    max_applicants: Optional[int]   = None
    applicant_type: Optional[ApplicantTypeEnum] = ApplicantTypeEnum.ANY
    ai_weight:      Optional[float] = 0.60


class GrantUpdate(BaseModel):
    title:          Optional[str]   = None
    description:    Optional[str]   = None
    budget:         Optional[float] = None
    currency:       Optional[str]   = None
    grant_value:    Optional[float] = None
    deadline:       Optional[datetime] = None
    max_applicants: Optional[int]   = None
    applicant_type: Optional[ApplicantTypeEnum] = None
    ai_weight:      Optional[float] = None


class QuestionInGrant(BaseModel):
    """Pyetjet e grantit — shfaqen kur aplikanti shikon grantin."""
    id:            UUID
    question_text: str
    question_type: str
    is_required:   bool
    order_no:      int

    model_config = {"from_attributes": True}


class CriteriaInGrant(BaseModel):
    id:          str
    name:        str
    weight:      int
    is_required: bool
    model_config = {"from_attributes": True}


class GrantResponse(BaseModel):
    id:             UUID
    title:          str
    description:    Optional[str]
    budget:         Optional[float]
    currency:       str
    grant_value:    Optional[float]
    deadline:       Optional[datetime]
    max_applicants: Optional[int]
    status:         GrantStatusEnum
    applicant_type: ApplicantTypeEnum
    ai_weight:      float
    created_at:     datetime
    tenant_slug:    Optional[str] = None
    org_name:       Optional[str] = None
    questions:      List[QuestionInGrant]  = []
    criteria:       List[CriteriaInGrant]  = []

    model_config = {"from_attributes": True}
