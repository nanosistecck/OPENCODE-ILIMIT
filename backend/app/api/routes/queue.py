"""Rotas do motor da fila e da integração com o OpenCode."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ...opencode.client import OpenCodeClient
from ...queue import persistence as store
from ...queue.engine import engine
from ..deps import get_db
from ..schemas import OpenCodeConfigIn, RetryIn

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/opencode/status")
def opencode_status(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    config = store.get_settings(conn)
    client = OpenCodeClient(config['executable'])
    return {
        **client.detect(),
        'capabilities': client.capabilities(),
        'configured': config,
    }


@router.get("/opencode/config")
def get_config(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return store.get_settings(conn)


@router.put("/opencode/config")
def put_config(payload: OpenCodeConfigIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return store.update_settings(conn, payload.model_dump(exclude_unset=True))


@router.post("/opencode/test")
def test_opencode(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    config = store.get_settings(conn)
    return OpenCodeClient(config['executable']).diagnostic()


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return engine.state(batch_id)


@router.post("/batches/{batch_id}/start")
async def start_batch(batch_id: str) -> dict:
    return await engine.start(batch_id)


@router.post("/batches/{batch_id}/pause")
async def pause_batch(batch_id: str) -> dict:
    return await engine.pause(batch_id)


@router.post("/batches/{batch_id}/resume")
async def resume_batch(batch_id: str) -> dict:
    return await engine.resume(batch_id)


@router.post("/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str) -> dict:
    return await engine.cancel(batch_id)


@router.post("/attempts/{attempt_id}/retry")
async def retry_attempt(attempt_id: str, payload: RetryIn | None = None) -> dict:
    return await engine.retry(attempt_id, bool(payload and payload.continueSession))


@router.get("/attempts/{attempt_id}/log")
def attempt_log(
    attempt_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=16000, ge=100, le=100000),
) -> dict:
    return store.read_log(attempt_id, offset, limit)


@router.get("/state")
def queue_state(
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    batches = conn.execute(
        'SELECT id FROM batches WHERE workspace_id = ? ORDER BY created_at DESC', (workspaceId,)
    ).fetchall()
    return {
        'workspaceId': workspaceId,
        'batches': [store.batch_state(conn, workspaceId, row['id']) for row in batches],
        'attempts': store.list_attempts(conn, workspaceId),
    }


@router.post("/recover")
def recover(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return store.recover_interrupted(conn)
