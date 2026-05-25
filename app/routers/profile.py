from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services import profile as profile_service

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=ProfileResponse)
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return profile_service.get_my_profile(current_user, db)


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    data: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return profile_service.update_my_profile(data, current_user, db)
