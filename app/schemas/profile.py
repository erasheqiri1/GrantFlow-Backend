from pydantic import BaseModel
from typing import Optional

from app.models.public.models import ApplicantType


class ProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    profile_picture: Optional[str] = None
    address: Optional[str] = None
    role: str
    tenant_slug: Optional[str] = None

    # ApplicantProfile
    applicant_type: Optional[ApplicantType] = None
    has_prev_grant: Optional[bool] = None
    description: Optional[str] = None

    # STUDENT
    university: Optional[str] = None
    faculty: Optional[str] = None
    study_program: Optional[str] = None
    study_level: Optional[str] = None
    study_year: Optional[int] = None
    study_status: Optional[str] = None

    # BUSINESS
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    activity_field: Optional[str] = None
    num_employees: Optional[str] = None
    founded_year: Optional[int] = None

    # ORGANIZATION
    org_name: Optional[str] = None
    org_type: Optional[str] = None
    org_field: Optional[str] = None
    num_staff: Optional[str] = None
    org_founded_year: Optional[int] = None
    reg_number: Optional[str] = None

    # INDIVIDUAL
    profession: Optional[str] = None
    experience_years: Optional[str] = None
    key_skills: Optional[str] = None
    portfolio_url: Optional[str] = None

    # OTHER
    role_title: Optional[str] = None
    interest_field: Optional[str] = None
    relevant_link: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    # user + user_profiles
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_picture: Optional[str] = None

    # applicant_profiles
    applicant_type: Optional[ApplicantType] = None
    has_prev_grant: Optional[bool] = None
    description: Optional[str] = None

    # STUDENT
    study_level: Optional[str] = None
    study_status: Optional[str] = None
    study_year: Optional[int] = None
    faculty: Optional[str] = None
    study_program: Optional[str] = None
    university: Optional[str] = None

    # BUSINESS
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    activity_field: Optional[str] = None
    num_employees: Optional[str] = None
    founded_year: Optional[int] = None

    # ORGANIZATION (OJQ)
    org_name: Optional[str] = None
    org_type: Optional[str] = None
    org_field: Optional[str] = None
    num_staff: Optional[str] = None
    org_founded_year: Optional[int] = None
    reg_number: Optional[str] = None

    # INDIVIDUAL
    profession: Optional[str] = None
    experience_years: Optional[str] = None
    key_skills: Optional[str] = None
    portfolio_url: Optional[str] = None
    cv_path: Optional[str] = None

    # OTHER
    role_title: Optional[str] = None
    interest_field: Optional[str] = None
    relevant_link: Optional[str] = None
