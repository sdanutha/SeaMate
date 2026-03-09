"""
Tool registry — every tool function lives here.

Add new tools by:
1. Define the @tool function
2. Add its name → callable to TOOL_REGISTRY
3. Reference the name in agents.yaml
"""

import io
import os
import contextlib
import subprocess

from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

_ddg = DuckDuckGoSearchRun()


@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo. Returns a summary of results."""
    return _ddg.run(query)


@tool
def run_command(command: str) -> str:
    """Run a shell command in the terminal and return its output.

    Use this for any terminal/CLI task: ls, cat, pip, git, curl, etc.
    The command runs in a bash shell with a 30-second timeout.
    Requires approval before execution.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
        if not output:
            output = f"(exit code {result.returncode}, no output)"
        return output[:4000]  # cap output length
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {e}"


@tool
def python_repl(code: str) -> str:
    """Execute a Python code snippet and return its stdout output.

    Pass the full Python code as a single string.
    Example: python_repl(code="print(2 + 2)")
    Requires approval before execution.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {"__builtins__": __builtins__})  # noqa: S102
        return buf.getvalue() or "(no output)"
    except Exception as e:
        return f"Error: {e}"


@tool
def read_file(path: str) -> str:
    """Read a file from disk and return its contents."""
    try:
        with open(path) as f:
            content = f.read()
        if len(content) > 8000:
            return content[:8000] + f"\n... (truncated, {len(content)} chars total)"
        return content
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file on disk. Requires approval."""
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error: {e}"


# ── Registry ─────────────────────────────────────────────────────────────────
# Map tool name (string in YAML) → callable tool object

TOOL_REGISTRY: dict[str, callable] = {
    "web_search": web_search,
    "python_repl": python_repl,
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
}
