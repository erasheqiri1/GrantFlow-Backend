from uuid import UUID
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    role: Optional[str]
    created_at: datetime
    tenant_status: Optional[str] = None

    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    role: Optional[str]
    created_at: datetime
    phone: Optional[str]
    profile_picture: Optional[str]
    address: Optional[str]
    tenant_name: Optional[str]
    tenant_slug: Optional[str]
    applicant_type: Optional[str]
    has_prev_grant: Optional[bool]
    description: Optional[str]
    study_level: Optional[str]
    study_status: Optional[str]
    study_year: Optional[int]
    faculty: Optional[str]
    study_program: Optional[str]
    university: Optional[str]
    business_name: Optional[str]
    business_type: Optional[str]
    activity_field: Optional[str]
    num_employees: Optional[str]
    founded_year: Optional[int]
    org_name: Optional[str]
    org_type: Optional[str]
    org_field: Optional[str]
    num_staff: Optional[str]
    org_founded_year: Optional[int]
    reg_number: Optional[str]
    profession: Optional[str]
    experience_years: Optional[str]
    key_skills: Optional[str]
    portfolio_url: Optional[str]
    cv_path: Optional[str]
    role_title: Optional[str]
    interest_field: Optional[str]
    relevant_link: Optional[str]


class UserListResponse(BaseModel):
    total: int
    page:  int
    size:  int
    items: List[UserResponse]
