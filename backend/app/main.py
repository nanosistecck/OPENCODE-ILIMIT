"""Aplicação FastAPI. Escuta em loopback por padrão; publicação fica para o Prompt 04."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import assistant, batches, delivery, discovery, git, health, plans, projects, queue, workspaces
from .config import settings
from .db.connection import connect
from .db.migrations import run_migrations
from .domain.errors import DomainError
from .remote.middleware import RemoteGuard
from .remote.routes import router as remote_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = connect()
    try:
        run_migrations(conn)
        from .queue.persistence import recover_interrupted

        recover_interrupted(conn)
    finally:
        conn.close()
    yield


app = FastAPI(
    title="OPENCODE ILIMIT API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(RemoteGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *settings.remote_allowed_origins,
        *([settings.remote_public_origin] if settings.remote_public_origin else []),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"code": exc.code, "message": exc.message, "detail": exc.detail},
    )


app.include_router(health.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(batches.router, prefix="/api")
app.include_router(git.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(delivery.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(remote_router)

# Build do React servido pela mesma origem pública quando existir.
_dist = Path(__file__).resolve().parents[2] / 'dist'
if _dist.is_dir():
    app.mount('/', StaticFiles(directory=str(_dist), html=True), name='painel')
