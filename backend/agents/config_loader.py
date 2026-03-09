"""
Config loader — reads agents.yaml and produces an AgentTeamConfig.

Supports:
- Environment variable interpolation: ${VAR:-default}
- Tool resolution: tool name strings → callable objects from TOOL_REGISTRY
- Skill paths: passed through as-is (paths to SKILL.md directories)
- Auto-generated orchestrator prompt from subagent list
"""

import os
import re
from dataclasses import dataclass, field

import yaml

from .tools import TOOL_REGISTRY


@dataclass
class SubagentConfig:
    """Configuration for a single subagent."""

    name: str
    description: str
    system_prompt: str
    tools: list             # resolved callable tool objects
    skills: list[str]       # paths to skill directories (SKILL.md)


@dataclass
class AgentTeamConfig:
    """Complete agent team configuration."""

    orchestrator_name: str
    orchestrator_description: str
    orchestrator_prompt: str        # auto-generated or explicit
    orchestrator_tools: list        # resolved callable tool objects
    orchestrator_skills: list[str]  # paths to skill directories (SKILL.md)
    subagents: list[SubagentConfig]
    interrupt_on: dict[str, bool]
    model_name: str
    model_base_url: str


def load_config(path: str) -> AgentTeamConfig:
    """Load agents.yaml → AgentTeamConfig with resolved tools and env vars."""
    with open(path) as f:
        raw_text = f.read()

    # Resolve env vars before parsing YAML
    resolved_text = _resolve_env_vars(raw_text)
    raw = yaml.safe_load(resolved_text)

    # ── Model ────────────────────────────────────────────────────────────
    model = raw.get("model", {})
    model_name = model.get("name", "gpt-oss:20b")
    model_base_url = model.get("base_url", "http://localhost:11434")

    # ── Subagents ────────────────────────────────────────────────────────
    subagents: list[SubagentConfig] = []
    for sa in raw.get("subagents", []):
        tools = [_resolve_tool(name) for name in sa.get("tools", [])]
        skills = sa.get("skills", [])
        subagents.append(
            SubagentConfig(
                name=sa["name"],
                description=sa.get("description", ""),
                system_prompt=sa.get("system_prompt", "").strip(),
                tools=tools,
                skills=skills,
            )
        )

    if not subagents:
        raise ValueError("agents.yaml must define at least one subagent")

    # ── Orchestrator ─────────────────────────────────────────────────────
    orch = raw.get("orchestrator", {})
    orch_name = orch.get("name", "seamate")
    orch_desc = orch.get("description", "AI orchestrator")
    orch_prompt = orch.get("system_prompt")
    if orch_prompt:
        orch_prompt = orch_prompt.strip()
    else:
        orch_prompt = _generate_prompt(orch_name, orch_desc, subagents)

    orch_tools = [_resolve_tool(name) for name in orch.get("tools", [])]
    orch_skills = orch.get("skills", [])

    # ── Interrupt rules ──────────────────────────────────────────────────
    interrupt_list = raw.get("interrupt_on", [])
    interrupt_on = {name: True for name in interrupt_list}

    return AgentTeamConfig(
        orchestrator_name=orch_name,
        orchestrator_description=orch_desc,
        orchestrator_prompt=orch_prompt,
        orchestrator_tools=orch_tools,
        orchestrator_skills=orch_skills,
        subagents=subagents,
        interrupt_on=interrupt_on,
        model_name=model_name,
        model_base_url=model_base_url,
    )


# ── Private helpers ──────────────────────────────────────────────────────────


def _resolve_tool(name: str):
    """Look up a tool name in the registry."""
    if name not in TOOL_REGISTRY:
        available = ", ".join(sorted(TOOL_REGISTRY.keys()))
        raise ValueError(
            f"Unknown tool '{name}' in agents.yaml. Available tools: {available}"
        )
    return TOOL_REGISTRY[name]


def _resolve_env_vars(text: str) -> str:
    """Replace ${VAR:-default} patterns with environment values."""

    def _replacer(match):
        var_name = match.group(1)
        default = match.group(3) or ""
        return os.environ.get(var_name, default)

    return re.sub(r"\$\{(\w+)(:-([^}]*))?\}", _replacer, text)


def _generate_prompt(
    name: str, description: str, subagents: list[SubagentConfig]
) -> str:
    """Auto-generate an orchestrator system prompt from the subagent list."""
    lines = [
        f"You are {name}, {description}.",
        "",
        "You coordinate a team of specialized subagents:",
    ]
    for sa in subagents:
        lines.append(f"- {sa.name:15s}: {sa.description}")
    lines += [
        "",
        "Guidelines:",
        "- Decompose complex tasks and delegate to the right subagent.",
        "- For terminal/CLI tasks, delegate to the coder subagent.",
        "- Always explain what you are doing and why.",
        "- Be concise but thorough in your final answers.",
        "- When a subagent finishes, summarize its findings for the user.",
    ]
    return "\n".join(lines)
