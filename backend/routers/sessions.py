from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.sessions import create_session, list_sessions, update_title, delete_session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateBody(BaseModel):
    title: str = "New session"


class PatchBody(BaseModel):
    title: str


@router.get("/")
def get_sessions():
    return list_sessions()


@router.post("/")
def new_session(body: CreateBody):
    return create_session(body.title)


@router.patch("/{session_id}")
def rename_session(session_id: str, body: PatchBody):
    updated = update_title(session_id, body.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.delete("/{session_id}")
def remove_session(session_id: str):
    delete_session(session_id)
    return {"status": "deleted"}
