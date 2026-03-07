from fastapi import APIRouter
from agents.registry import list_groups

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/")
def get_all_agents():
    return list_groups()
