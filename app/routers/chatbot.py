from typing import List, Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.services import chatbot as chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    message: str
    history: List[HistoryMessage] = []


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    user=Depends(require_permission("applications:read_own")),
    db: Session = Depends(get_db),
):
    """Chatbot për aplikantët — sugjeron grante bazuar në profilin e userit."""
    if not data.message or not data.message.strip():
        return ChatResponse(reply="Shkruaj diçka që të mund të të ndihmoj.")

    reply = chatbot_service.chat(
        user["user_id"],
        data.message.strip(),
        db,
        history=[{"role": h.role, "text": h.text} for h in data.history],
    )
    return ChatResponse(reply=reply)
