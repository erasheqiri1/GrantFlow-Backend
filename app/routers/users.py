from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.users import UserListResponse, UserDetailResponse
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["Users"])


class CreateSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class InviteSuperAdminRequest(BaseModel):
    email: EmailStr


@router.get("", response_model=UserListResponse)
def list_users(
    sortBy:  str = Query("created_at", description="created_at | email | first_name | last_name"),
    sortDir: str = Query("desc",       description="asc | desc"),
    page:    int = Query(1,  ge=1),
    size:    int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("users:read")),
):
    return users_service.get_users(db, sortBy, sortDir, page, size)


@router.post("/super-admin")
def create_super_admin(data: CreateSuperAdminRequest, db: Session = Depends(get_db), _: dict = Depends(require_permission("users:assign_role"))):
    return users_service.create_super_admin(db, data)


@router.post("/invite-super-admin")
def invite_super_admin(data: InviteSuperAdminRequest, db: Session = Depends(get_db), current_user: dict = Depends(require_permission("users:assign_role"))):
    return users_service.invite_super_admin(db, data.email, current_user["user_id"])


@router.patch("/{user_id}/toggle-active")
def toggle_user_active(user_id: str, db: Session = Depends(get_db), current_user: dict = Depends(require_permission("users:deactivate"))):
    return users_service.toggle_user_active(db, user_id, current_user["user_id"])


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(user_id: str, db: Session = Depends(get_db), _: dict = Depends(require_permission("users:read"))):
    return users_service.get_user(db, user_id)
