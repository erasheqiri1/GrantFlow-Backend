from fastapi import APIRouter, Depends, HTTPException
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


@router.get("", response_model=UserListResponse, summary="Lista e të gjithë userëve")
def list_users(
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return users_service.get_users(db)


@router.get("/{user_id}", response_model=UserDetailResponse, summary="Detajet e një useri")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_super_admin),
):
    return users_service.get_user(db, user_id)
