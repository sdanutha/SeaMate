from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from agents.orchestrator import build_orchestrator
from routers.agents import router as agents_router
from routers.ws import router as ws_router

app = FastAPI(title="SeaMate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory checkpointer — no DB needed
app.state.graph = build_orchestrator(MemorySaver())

app.include_router(agents_router)
app.include_router(ws_router)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
