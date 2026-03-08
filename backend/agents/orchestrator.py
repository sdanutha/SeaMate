import os
import subprocess
import textwrap
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from deepagents import create_deep_agent

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_DEFAULT_MODEL   = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

# ── Tools ────────────────────────────────────────────────────────────────────

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
    import io
    import contextlib
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


# ── Subagents ────────────────────────────────────────────────────────────────

SUBAGENTS = [
    {
        "name": "researcher",
        "description": "Searches the web to gather information on a topic.",
        "system_prompt": "You are a research specialist. Use the web_search tool to find accurate, up-to-date information. Always cite your sources.",
        "tools": [web_search],
    },
    {
        "name": "coder",
        "description": "Writes and executes Python code or shell commands.",
        "system_prompt": textwrap.dedent("""\
            You are a code and terminal specialist.

            You have two tools:
            - python_repl: Execute Python code. Pass code as a string argument.
              Example: python_repl(code="print('hello')")
            - run_command: Execute a shell/terminal command.
              Example: run_command(command="ls -la")

            Choose the right tool for the task. Use run_command for terminal tasks
            (ls, cat, pip, git, curl, etc.) and python_repl for Python scripts.
        """).strip(),
        "tools": [python_repl, run_command],
    },
    {
        "name": "file-manager",
        "description": "Reads and writes files on the local filesystem.",
        "system_prompt": "You are a file management specialist. Use read_file and write_file carefully.",
        "tools": [read_file, write_file],
    },
]

# ── Orchestrator prompt ──────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = textwrap.dedent("""\
    You are SeaMate, an intelligent orchestrator for Seagate's digital workforce.

    You coordinate a team of specialized subagents:
    - researcher    : searches the web for information
    - coder         : runs Python code or shell/terminal commands
    - file-manager  : reads and writes files

    Guidelines:
    - Decompose complex tasks and delegate to the right subagent.
    - For terminal/CLI tasks, delegate to the coder subagent.
    - Always explain what you are doing and why.
    - Be concise but thorough in your final answers.
    - When a subagent finishes, summarize its findings for the user.
""").strip()


# ── Factory ──────────────────────────────────────────────────────────────────


def build_orchestrator(checkpointer):
    """Build a new orchestrator graph using the provided async checkpointer."""
    llm = ChatOllama(model=_DEFAULT_MODEL, base_url=_OLLAMA_BASE_URL)
    return create_deep_agent(
        model=llm,
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=SUBAGENTS,
        checkpointer=checkpointer,
        interrupt_on={
            "python_repl": True,
            "run_command": True,
            "write_file": True,
        },
    )
