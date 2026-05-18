import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.public.models import User, UserProfile, ApplicantProfile
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

APPLICANT_FIELDS = [
    "applicant_type", "has_prev_grant", "description",
    "study_level", "study_status", "study_year", "faculty", "study_program", "university",
    "business_name", "business_type", "activity_field", "num_employees", "founded_year",
    "org_name", "org_type", "org_field", "num_staff", "org_founded_year", "reg_number",
    "profession", "experience_years", "key_skills", "portfolio_url", "cv_path",
    "role_title", "interest_field", "relevant_link",
]


def get_my_profile(current_user: dict, db: Session) -> ProfileResponse:
    user_id = uuid.UUID(current_user["user_id"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Useri nuk u gjet")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=profile.phone if profile else None,
        profile_picture=profile.profile_picture if profile else None,
        address=profile.address if profile else None,
        role=current_user["role"],
        tenant_slug=current_user["tenant_slug"],
    )


def update_my_profile(data: ProfileUpdateRequest, current_user: dict, db: Session) -> ProfileResponse:
    user_id = uuid.UUID(current_user["user_id"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Useri nuk u gjet")

    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    if data.phone is not None:
        profile.phone = data.phone
    if data.address is not None:
        profile.address = data.address
    if data.profile_picture is not None:
        profile.profile_picture = data.profile_picture

    if current_user["role"] == "APPLICANT":
        applicant = db.query(ApplicantProfile).filter(ApplicantProfile.user_id == user_id).first()
        if applicant is None:
            applicant = ApplicantProfile(user_id=user_id)
            db.add(applicant)

        for field in APPLICANT_FIELDS:
            value = getattr(data, field)
            if value is not None:
                setattr(applicant, field, value)

    db.commit()

    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=profile.phone,
        profile_picture=profile.profile_picture,
        address=profile.address,
        role=current_user["role"],
        tenant_slug=current_user["tenant_slug"],
    )
