"""
Agent registry — builds the /api/agents/ response from config.

tools and skills are reported separately:
- tools: [{name, description}] — callable Python functions
- skills: [{name, description}] — parsed from SKILL.md frontmatter
"""

import logging
import re
from pathlib import Path

import yaml

from .config_loader import AgentTeamConfig

logger = logging.getLogger(__name__)

# Base directory for resolving relative skill paths (backend/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent


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
                "skills": _scan_skill_sources(config.orchestrator_skills),
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
                "skills": _scan_skill_sources(sa.skills),
            }
            for sa in config.subagents
        ],
    }


# ── Skill scanner ────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _scan_skill_sources(source_paths: list[str]) -> list[dict]:
    """Scan skill source directories and return [{name, description}].

    Later sources override earlier ones (last-one-wins), matching
    the DeepAgents SkillsMiddleware behaviour.
    """
    skills: dict[str, dict] = {}  # name → {name, description}

    for source_path in source_paths:
        resolved = _BACKEND_DIR / source_path
        if not resolved.is_dir():
            continue

        for skill_dir in sorted(resolved.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            meta = _parse_frontmatter(skill_md)
            if meta:
                skills[meta["name"]] = meta  # last-one-wins

    return list(skills.values())


def _parse_frontmatter(path: Path) -> dict | None:
    """Read a SKILL.md and extract {name, description} from YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    match = _FRONTMATTER_RE.search(text)
    if not match:
        return None

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        logger.warning("Bad YAML in %s: %s", path, exc)
        return None

    if not isinstance(data, dict):
        return None

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()

    if not name or not description:
        return None

    return {"name": name, "description": description}
