# SeaMate — Multi-Agent Workspace

A real-time multi-agent chat application powered by **DeepAgents** + **LangGraph** + **Ollama**.
The user talks to a single **orchestrator** agent that automatically delegates tasks to specialized **subagents**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Plain HTML/JS)                                │
│                                                         │
│  index.html ─► app.js ─► ws.js (ChatSocket)             │
│       │             │          │                        │
│       │             │          └──── WebSocket /ws ──────┼──┐
│       │             └── fetch /api/agents/ ──────────────┼──┤
│       └── style.css (Seagate theme, dark/light)         │  │
└─────────────────────────────────────────────────────────┘  │
                                                             │
┌─────────────────────────────────────────────────────────┐  │
│  FastAPI Backend (uvicorn)                              │◄─┘
│                                                         │
│  main.py                                                │
│    ├── routers/ws.py       ← WebSocket /ws              │
│    ├── routers/agents.py   ← GET /api/agents/           │
│    └── StaticFiles("/")    ← serves frontend/           │
│                                                         │
│  agents/orchestrator.py                                 │
│    └── build_orchestrator(checkpointer)                 │
│         ├── ChatOllama (LLM)                            │
│         ├── create_deep_agent()                         │
│         └── subagents: researcher, coder, file-manager  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Ollama (local LLM)  │
│  model: gpt-oss:20b  │
│  :11434              │
└──────────────────────┘
```

---

## Data Flow

### 1. User sends a message

```
Browser                     Backend
───────                     ───────
msg-input ──► ChatSocket.sendMessage(text)
                │
                └─► ws.send({ type: "message", message: text })
                         │
                         ▼
                    ws.py: websocket.receive_text()
                         │
                         ▼
                    graph.astream(
                      {"messages": [{"role":"user","content": text}]},
                      config={"configurable": {"thread_id": uuid}},
                      stream_mode="messages",
                      subgraphs=True
                    )
```

### 2. Orchestrator processes the message

```
DeepAgent Orchestrator (LangGraph CompiledStateGraph)
    │
    ├── LLM decides if it can answer directly
    │     └── streams AIMessageChunk tokens ──► ws.send({type:"token"})
    │
    └── LLM delegates to a subagent
          ├── researcher ──► web_search (DuckDuckGo)
          ├── coder ──► python_repl (exec Python)
          └── file-manager ──► read_file / write_file
```

### 3. Tokens stream back to the browser

```
Backend                          Browser
───────                          ───────
ws.send({type:"agent_start"})  ──► createStreamBubble()
ws.send({type:"token", content}) ──► appendToken() + marked.parse()
ws.send({type:"token", content}) ──► appendToken() + marked.parse()
  ...
ws.send({type:"agent_end"})    ──► finalizeStreamBubble()
                                     └── re-enable input
```

---

## Project Structure

```
maw/
├── backend/
│   ├── main.py                 # FastAPI app — entry point
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # OLLAMA_BASE_URL, OLLAMA_MODEL
│   ├── .env.example
│   ├── agents/
│   │   ├── orchestrator.py     # build_orchestrator() — DeepAgent + subagents
│   │   ├── base_agent.py       # SUBAGENT_NAMES list
│   │   └── registry.py         # AGENT_GROUPS for sidebar API
│   └── routers/
│       ├── ws.py               # WebSocket /ws — streaming chat
│       └── agents.py           # GET /api/agents/ — agent list
│
├── frontend/
│   ├── index.html              # Single-page layout
│   ├── css/
│   │   └── style.css           # Seagate-inspired theme (dark/light)
│   └── js/
│       ├── app.js              # Chat UI logic, theme toggle
│       └── ws.js               # ChatSocket — WebSocket wrapper
│
└── README.md
```

---

## Key Files Explained

### Backend

| File | Purpose |
|------|---------|
| `main.py` | Creates FastAPI app, builds orchestrator with `MemorySaver`, mounts frontend as static files |
| `agents/orchestrator.py` | Defines tools (`web_search`, `python_repl`, `read_file`, `write_file`), subagent configs, orchestrator system prompt, and the `build_orchestrator()` factory |
| `agents/registry.py` | Returns agent groups (orchestrator + subagents) for the sidebar API |
| `routers/ws.py` | Single `/ws` WebSocket endpoint — receives user messages, streams LLM tokens back in real-time |
| `routers/agents.py` | `GET /api/agents/` — returns agent catalogue as JSON |

### Frontend

| File | Purpose |
|------|---------|
| `index.html` | Minimal layout: topbar (logo + theme toggle + status), sidebar (agent list), chat output, input bar |
| `js/app.js` | Connects WebSocket on load, renders chat bubbles with markdown (via `marked.js`), handles theme toggle with `localStorage` |
| `js/ws.js` | `ChatSocket` class — connects to `/ws`, routes incoming messages by type (`status`, `agent_start`, `token`, `agent_end`, `error`) |
| `css/style.css` | CSS custom properties for dark/light themes, Seagate brand colors (`#6EBE49` green, `#008F98` teal, `#00A1DD` cyan), Inter font |

---

## WebSocket Protocol

### Client → Server

| type | payload | description |
|------|---------|-------------|
| `message` | `{ message: string }` | User chat message |

### Server → Client

| type | payload | description |
|------|---------|-------------|
| `status` | `{ content: string }` | Connection status |
| `agent_start` | `{}` | Orchestrator begins responding |
| `token` | `{ content: string }` | Streaming text token (AI) |
| `agent_end` | `{}` | Orchestrator finished |
| `error` | `{ content: string }` | Error message |

---

## Subagents

| Name | Tools | Description |
|------|-------|-------------|
| `researcher` | `web_search` (DuckDuckGo) | Web research — searches and summarizes results |
| `coder` | `python_repl` | Executes Python code (with `interrupt_on` for approval) |
| `file-manager` | `read_file`, `write_file` | Local file operations (with `interrupt_on` for write) |

The orchestrator automatically decides which subagent to invoke based on the user's request.
Tools marked with `interrupt_on` will pause for human approval before executing.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Ollama (`gpt-oss:20b` default) |
| Agent Framework | DeepAgents (`create_deep_agent`) |
| Graph Engine | LangGraph (`CompiledStateGraph`) |
| Checkpointer | `MemorySaver` (in-memory, no DB) |
| Backend | FastAPI + uvicorn |
| WebSocket | FastAPI native WebSocket |
| Frontend | Plain HTML + vanilla JS (no build step) |
| Markdown | `marked.js` via CDN |
| Styling | CSS custom properties, Seagate theme |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) running locally with a model pulled

### Setup

```bash
# 1. Clone and enter project
cd maw

# 2. Create virtual environment
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env to set your Ollama model and URL

# 5. Make sure Ollama is running
ollama serve                # if not already running
ollama pull gpt-oss:20b    # or your preferred model

# 6. Start the server
uvicorn main:app --port 3456 --reload
```

### Usage

1. Open `http://localhost:3456` in your browser
2. You'll see the SeaMate chat interface with a **LIVE** status
3. Type a message and press Enter
4. The orchestrator will respond — delegating to subagents when needed
5. Use the ☀/🌙 button to toggle dark/light mode

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `gpt-oss:20b` | LLM model name |
