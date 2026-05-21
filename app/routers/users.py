from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.users import UserListResponse, UserResponse, UserDetailResponse
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["Users"])


def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Vetëm SUPER_ADMIN ka qasje")
    return current_user


class CreateSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


@router.get("", response_model=UserListResponse, summary="Lista e të gjithë userëve")
def list_users(
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return users_service.get_users(db)


@router.post("/super-admin", summary="Krijo Super Admin të ri")
def create_super_admin(
    data: CreateSuperAdminRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return users_service.create_super_admin(db, data)


@router.patch("/{user_id}/toggle-active", summary="Aktivo / Deaktivo userin")
def toggle_user_active(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin),
):
    return users_service.toggle_user_active(db, user_id, current_user["user_id"])


@router.get("/{user_id}", response_model=UserDetailResponse, summary="Detajet e një useri")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return users_service.get_user(db, user_id)
