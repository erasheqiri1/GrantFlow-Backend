from pydantic import BaseModel, EmailStr
from typing import Literal, List
from uuid import UUID


class InviteRequest(BaseModel):
    email: EmailStr
    role: Literal["COMMISSIONER", "ORG_ADMIN"]


class TeamMemberResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str

    class Config:
        from_attributes = True


class PaginatedTeamResponse(BaseModel):
    total: int
    page:  int
    size:  int
    items: List[TeamMemberResponse]
