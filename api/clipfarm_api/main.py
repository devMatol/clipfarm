from __future__ import annotations

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .queue import procrastinate_app
from .routers import accounts, clips, media, projects, publishing, scheduling


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage : initialisation des tables SQLModel
    init_db()
    async with procrastinate_app.open_async():
        yield


app = FastAPI(
    title="ClipFarm API",
    description="API locale de génération de clips courts par IA",
    version="0.1.0",
    lifespan=lifespan,
)

# Configuration CORS pour Next.js (port 3000) et clients locaux
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(clips.router)
app.include_router(media.router)
app.include_router(accounts.router)
app.include_router(publishing.router)
app.include_router(scheduling.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "clipfarm-api"}
