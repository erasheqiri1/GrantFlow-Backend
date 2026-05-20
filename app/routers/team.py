from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission, get_tenant_db
from app.schemas.team import InviteRequest, TeamMemberResponse
from app.services import team as team_service

router = APIRouter(tags=["Team"])


@router.post("/invitations", status_code=202)
def invite_member(
    data: InviteRequest,
    current_user: dict = Depends(require_permission("invitations:send")),
    db: Session = Depends(get_tenant_db),
):
    return team_service.send_invite(data, current_user, db)


@router.get("/team", response_model=list[TeamMemberResponse])
def get_team(
    current_user: dict = Depends(require_permission("users:read")),
    db: Session = Depends(get_tenant_db),
):
    return team_service.get_team(current_user, db)


@router.delete("/team/{member_id}", status_code=204)
def remove_member(
    member_id: str,
    current_user: dict = Depends(require_permission("users:deactivate")),
    db: Session = Depends(get_tenant_db),
):
    team_service.remove_member(member_id, current_user, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
