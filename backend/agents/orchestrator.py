import os
import textwrap
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from deepagents import create_deep_agent

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_DEFAULT_MODEL   = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
_DB_PATH         = os.getenv("SEAMATE_DB", "seamate.db")

# ── Tools ────────────────────────────────────────────────────────────────────

_ddg = DuckDuckGoSearchRun()

@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo. Returns a summary of results."""
    return _ddg.run(query)


@tool
def python_repl(code: str) -> str:
    """Execute Python code and return stdout/result. Requires approval."""
    import io, contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {})  # noqa: S102
        return buf.getvalue() or "(no output)"
    except Exception as e:
        return f"Error: {e}"


@tool
def read_file(path: str) -> str:
    """Read a file from disk and return its contents."""
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file. Requires approval."""
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
        "description": "Writes and executes Python code to solve problems or process data.",
        "system_prompt": "You are a Python expert. Write clean, correct code and run it with python_repl. Show your reasoning.",
        "tools": [python_repl],
    },
    {
        "name": "file-manager",
        "description": "Reads and writes files on the local filesystem.",
        "system_prompt": "You are a file management specialist. Use read_file and write_file carefully.",
        "tools": [read_file, write_file],
    },
]

# ── Orchestrator prompt ──────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = textwrap.dedent("""
    You are SeaMate, an intelligent orchestrator for Seagate's digital workforce.

    You coordinate a team of specialized subagents:
    - researcher : searches the web for information
    - coder      : writes and runs Python code
    - file-manager : reads and writes files

    Guidelines:
    - Decompose complex tasks and delegate to the right subagent.
    - Always explain what you are doing and why.
    - Be concise but thorough in your final answers.
    - When a subagent finishes, summarize its findings for the user.
""").strip()


# ── Factory ──────────────────────────────────────────────────────────────────

_graph = None  # singleton


def get_orchestrator():
    global _graph
    if _graph is None:
        llm = ChatOllama(model=_DEFAULT_MODEL, base_url=_OLLAMA_BASE_URL)
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        _graph = create_deep_agent(
            model=llm,
            system_prompt=ORCHESTRATOR_PROMPT,
            subagents=SUBAGENTS,
            checkpointer=checkpointer,
            interrupt_on={
                "python_repl": True,
                "write_file": True,
            },
        )
    return _graph
