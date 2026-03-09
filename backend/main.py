from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from agents.config_loader import load_config
from agents.orchestrator import build_orchestrator
from agents.registry import build_agent_groups
from routers.agents import router as agents_router
from routers.ws import router as ws_router

app = FastAPI(title="SeaMate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load config & build graph ────────────────────────────────────────────────
config_path = Path(__file__).parent / "agents.yaml"
config = load_config(str(config_path))

app.state.graph = build_orchestrator(config, MemorySaver())
app.state.agent_groups = build_agent_groups(config)

app.include_router(agents_router)
app.include_router(ws_router)

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
