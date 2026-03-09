"""
Agent registry — builds the /api/agents/ response from config.

tools and skills are reported separately:
- tools: [{name, description}] — callable Python functions
- skills: [str] — paths to SKILL.md directories
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
                "tools": [
                    {
                        "name": getattr(t, "name", str(t)),
                        "description": getattr(t, "description", ""),
                    }
                    for t in config.orchestrator_tools
                ],
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
                "skills": sa.skills,
            }
            for sa in config.subagents
        ],
    }
