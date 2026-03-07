from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from db.sessions import init_db
from routers.agents import router as agents_router
from routers.sessions import router as sessions_router
from routers.ws import router as ws_router

app = FastAPI(title="SeaMate - Multi-Agent Workspace")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(agents_router)
app.include_router(sessions_router)
app.include_router(ws_router)

# Serve frontend static files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
