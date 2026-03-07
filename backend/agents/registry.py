from .base_agent import BaseAgent

# ตัวอย่าง agents จัดกลุ่มแบบ MAW
AGENT_GROUPS = {
    "1-ORACLES": [
        BaseAgent("pulse-oracle", "pulse-oracle", "You are Pulse Oracle, a real-time monitoring assistant. Respond concisely."),
        BaseAgent("nexus-oracle", "nexus-oracle", "You are Nexus Oracle, a connectivity and integration specialist. Respond concisely."),
        BaseAgent("neo-oracle", "neo-oracle", "You are Neo Oracle, a modern AI assistant. Respond concisely."),
    ],
    "2-TOOLS": [
        BaseAgent("skills-cli", "skills-cli", "You are a CLI skills assistant that helps with command-line tasks. Respond concisely."),
    ],
}

# flat lookup
_agent_map: dict[str, BaseAgent] = {}
for group_agents in AGENT_GROUPS.values():
    for agent in group_agents:
        _agent_map[agent.agent_id] = agent


def get_agent(agent_id: str) -> BaseAgent | None:
    return _agent_map.get(agent_id)


def list_groups() -> dict:
    return {
        group: [a.to_dict() for a in agents]
        for group, agents in AGENT_GROUPS.items()
    }
