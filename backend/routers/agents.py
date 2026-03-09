from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/")
def get_all_agents(request: Request):
    return request.app.state.agent_groups
