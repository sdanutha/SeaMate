# base_agent.py — kept for backward compatibility
# The main agent is now the orchestrator (agents/orchestrator.py).

from .orchestrator import SUBAGENTS

SUBAGENT_NAMES = [sa["name"] for sa in SUBAGENTS]
