---
name: _example
description: >
  This is a template skill. Copy this folder, rename it, and edit the fields
  below to create your own skill. The folder name must match the "name" field.
license: MIT
compatibility: Python 3.10+
allowed-tools: web_search
metadata:
  author: SeaMate Team
  version: "1.0"
---

# Example Skill

## When to Use

Describe when the agent should activate this skill.

## Instructions

Step-by-step instructions for the agent to follow.

1. First, do this...
2. Then, do that...
3. Finally, summarize...

## Notes

- This file uses **YAML frontmatter** (between the `---` markers) for metadata.
- The markdown body below the frontmatter is the actual skill instructions.
- Agents see only `name` + `description` first (progressive disclosure).
- The full markdown is loaded on-demand when the agent needs detailed instructions.
