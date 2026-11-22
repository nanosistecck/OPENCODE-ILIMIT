"""Rotas de commit, publicação e pull request."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ...delivery import service
from ..deps import get_db
from ..schemas import (
    DeliveryCommitIn, DeliveryPreviewIn, DeliveryPrIn, DeliveryPrPreviewIn,
    DeliveryPrRefreshIn, DeliveryPushIn,
)

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/state")
def delivery_state(workspaceId: str = Query(..., alias="workspaceId"),
                   conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.state(conn, workspaceId)


@router.post("/preview")
def preview(payload: DeliveryPreviewIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.preview(conn, payload.workspaceId, payload.selectedPaths, payload.message)


@router.post("/commit")
def commit(payload: DeliveryCommitIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.commit(
        conn, payload.workspaceId, payload.previewId, payload.selectedPaths,
        payload.message, payload.batchId or '', payload.attemptId or '',
    )


@router.post("/push")
def push(payload: DeliveryPushIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.push(conn, payload.workspaceId, payload.remote or '', payload.commitId or '')


@router.post("/pr/preview")
def pr_preview(payload: DeliveryPrPreviewIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.pr_preview(conn, payload.workspaceId, payload.base)


@router.post("/pr")
def create_pr(payload: DeliveryPrIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.create_pr(
        conn, payload.workspaceId, payload.title, payload.body,
        payload.base, payload.draft, payload.forceNew,
    )


@router.post("/pr/refresh")
def refresh_pr(payload: DeliveryPrRefreshIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.refresh_pr(conn, payload.workspaceId)
