from typing import List, Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.services.chatbot import ChatService

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    message: str
    history: List[HistoryMessage] = []


class ChatResponse(BaseModel):
    reply: str


@router.post(
    "",
    response_model=ChatResponse,
    summary="Chatbot AI për aplikantët",
    description="""
Dërgon mesazh te chatbot-i AI dhe merr përgjigje.

**Kërkon rolin:** `APPLICANT`

Chatbot-i sugjeron grante të përshtatshme bazuar në profilin e userit dhe historinë e bisedës.
""",
    responses={
        200: {"description": "Përgjigja e chatbot-it"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet APPLICANT"},
    },
)
def chat(
    data: ChatRequest,
    user=Depends(require_permission("applications:read_own")),
    db: Session = Depends(get_db),
):
    if not data.message or not data.message.strip():
        return ChatResponse(reply="Shkruaj diçka që të mund të të ndihmoj.")

    reply = ChatService(db).chat(
        user["user_id"],
        data.message.strip(),
        history=[{"role": h.role, "text": h.text} for h in data.history],
    )
    return ChatResponse(reply=reply)
