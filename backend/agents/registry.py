"""
Agent registry — builds the /api/agents/ response from config.
"""

from .config_loader import AgentTeamConfig


def build_agent_groups(config: AgentTeamConfig) -> dict:
    """Build the agent catalogue dict used by the sidebar API."""
    return {
        "orchestrator": [
            {
                "id": config.orchestrator_name,
                "name": config.orchestrator_name,
                "role": "orchestrator",
                "system_prompt": config.orchestrator_prompt,
                "tools": [],
                "skills": config.orchestrator_skills,
            }
        ],
        "subagents": [
            {
                "id": sa.name,
                "name": sa.name,
                "role": "subagent",
                "system_prompt": sa.system_prompt,
                "tools": [
                    {
                        "name": getattr(t, "name", str(t)),
                        "description": getattr(t, "description", ""),
                    }
                    for t in sa.tools
                ],
                "skills": [getattr(t, "name", str(t)) for t in sa.tools],
            }
            for sa in config.subagents
        ],
    }
