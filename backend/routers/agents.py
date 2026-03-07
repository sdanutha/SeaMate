from fastapi import APIRouter, HTTPException
from agents.registry import list_groups, get_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/")
def get_all_agents():
    return list_groups()


@router.get("/{agent_id}")
def get_agent_info(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


@router.post("/{agent_id}/clear")
def clear_history(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.clear_history()
    return {"status": "cleared"}
