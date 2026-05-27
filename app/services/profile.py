import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.public.models import User, UserProfile, ApplicantProfile
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

APPLICANT_FIELDS = [

    "applicant_type", "has_prev_grant", "description", "personal_id",
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

    applicant_profile = db.query(ApplicantProfile).filter(ApplicantProfile.user_id == user_id).first()

    ap = applicant_profile  # shorthand

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
        # ApplicantProfile
        personal_id=ap.personal_id if ap else None,
        applicant_type=ap.applicant_type if ap else None,
        has_prev_grant=ap.has_prev_grant if ap else None,
        description=ap.description if ap else None,
        university=ap.university if ap else None,
        faculty=ap.faculty if ap else None,
        study_program=ap.study_program if ap else None,
        study_level=ap.study_level if ap else None,
        study_year=ap.study_year if ap else None,
        study_status=ap.study_status if ap else None,
        business_name=ap.business_name if ap else None,
        business_type=ap.business_type if ap else None,
        activity_field=ap.activity_field if ap else None,
        num_employees=ap.num_employees if ap else None,
        founded_year=ap.founded_year if ap else None,
        org_name=ap.org_name if ap else None,
        org_type=ap.org_type if ap else None,
        org_field=ap.org_field if ap else None,
        num_staff=ap.num_staff if ap else None,
        org_founded_year=ap.org_founded_year if ap else None,
        reg_number=ap.reg_number if ap else None,
        profession=ap.profession if ap else None,
        experience_years=ap.experience_years if ap else None,
        key_skills=ap.key_skills if ap else None,
        portfolio_url=ap.portfolio_url if ap else None,
        role_title=ap.role_title if ap else None,
        interest_field=ap.interest_field if ap else None,
        relevant_link=ap.relevant_link if ap else None,
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

        # Nëse po ndryshon kategoria, pastron fushat specifike të kategorisë së vjetër
        TYPE_SPECIFIC_FIELDS = [
            "study_level", "study_status", "study_year", "faculty", "study_program", "university",
            "business_name", "business_type", "activity_field", "num_employees", "founded_year",
            "org_name", "org_type", "org_field", "num_staff", "org_founded_year", "reg_number",
            "profession", "experience_years", "key_skills", "portfolio_url", "cv_path",
            "role_title", "interest_field", "relevant_link",
        ]
        if data.applicant_type is not None and applicant.applicant_type != data.applicant_type:
            for field in TYPE_SPECIFIC_FIELDS:
                setattr(applicant, field, None)

        for field in APPLICANT_FIELDS:
            value = getattr(data, field)
            if value is not None:
                setattr(applicant, field, value)

    db.commit()

    return get_my_profile(current_user, db)
