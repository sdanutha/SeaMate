from .orchestrator import SUBAGENTS, ORCHESTRATOR_PROMPT

# ── Build catalogue from orchestrator config ────────────────────────────────

def _tool_info(t):
    """Extract tool name and description from a LangChain tool."""
    return {
        "name": getattr(t, "name", str(t)),
        "description": getattr(t, "description", ""),
    }


AGENT_GROUPS = {
    "orchestrator": [
        {
            "id": "seamate",
            "name": "seamate",
            "role": "orchestrator",
            "system_prompt": ORCHESTRATOR_PROMPT,
            "tools": [],
            "skills": ["delegate tasks", "coordinate subagents", "summarize results"],
        },
    ],
    "subagents": [
        {
            "id": sa["name"],
            "name": sa["name"],
            "role": "subagent",
            "system_prompt": sa.get("system_prompt", ""),
            "tools": [_tool_info(t) for t in sa.get("tools", [])],
            "skills": [],
        }
        for sa in SUBAGENTS
    ],
}

# Add human-readable skills based on tools
for sa in AGENT_GROUPS["subagents"]:
    sa["skills"] = [t["name"] for t in sa["tools"]]


def list_groups() -> dict:
    return AGENT_GROUPS
