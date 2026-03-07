from .base_agent import SUBAGENT_NAMES

# SeaMate agent catalogue exposed to the frontend
AGENT_GROUPS = {
    "orchestrator": [
        {"id": "seamate", "name": "seamate", "role": "orchestrator"},
    ],
    "subagents": [
        {"id": name, "name": name, "role": "subagent"}
        for name in SUBAGENT_NAMES
    ],
}


def list_groups() -> dict:
    return AGENT_GROUPS
