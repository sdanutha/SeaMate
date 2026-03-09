"""
Orchestrator factory — builds the LangGraph agent from config.
"""

from langchain_ollama import ChatOllama
from deepagents import create_deep_agent

from .config_loader import AgentTeamConfig


def build_orchestrator(config: AgentTeamConfig, checkpointer):
    """Build the orchestrator graph from an AgentTeamConfig."""
    llm = ChatOllama(model=config.model_name, base_url=config.model_base_url)

    subagents = [
        {
            "name": sa.name,
            "description": sa.description,
            "system_prompt": sa.system_prompt,
            "tools": sa.tools,
        }
        for sa in config.subagents
    ]

    return create_deep_agent(
        model=llm,
        system_prompt=config.orchestrator_prompt,
        subagents=subagents,
        checkpointer=checkpointer,
        interrupt_on=config.interrupt_on,
    )
