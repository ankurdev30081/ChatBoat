import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChatMessage, ChatSession
from app.rag.llm import chat_completion
from app.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

HISTORY_TURNS = 6


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        session_id = req.session_id or str(uuid.uuid4())
        session = db.get(ChatSession, session_id)
        if session is None:
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit()

        history_rows = (
            db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(HISTORY_TURNS)
            )
            .scalars()
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

        context, sources = retrieve_context(req.message)
        reply = await chat_completion(context, history, req.message)

        db.add(ChatMessage(session_id=session_id, role="user", content=req.message))
        db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
        db.commit()

        return ChatResponse(reply=reply, session_id=session_id, sources=sources)
    except Exception as e:
        logger.error(f"Error processing chat message: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

