from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ...domain import batches as rules
from ..deps import get_db
from ..schemas import BatchIn, BatchOut, NewQueueItemIn, QueueItemPatch, ReorderIn
from ..serializers import batch_out

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchIn | None = None,
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    name = (payload.name or payload.title) if payload else None
    name = name or "Lote manual"
    batch = rules.create_batch(conn, workspaceId, name)
    return batch_out(conn, workspaceId, batch)


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(
    batch_id: str,
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    return batch_out(conn, workspaceId, rules.get_batch(conn, workspaceId, batch_id))


@router.post("/{batch_id}/items", response_model=BatchOut)
def add_items(
    batch_id: str,
    items: list[NewQueueItemIn],
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    result = rules.add_items(
        conn, workspaceId, batch_id, [item.model_dump() for item in items]
    )
    return batch_out(conn, workspaceId, result)


@router.patch("/{batch_id}/items/{item_id}", response_model=BatchOut)
def update_item(
    batch_id: str,
    item_id: str,
    payload: QueueItemPatch,
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "fileName" in patch:
        patch["fileName"] = patch.pop("fileName")
    result = rules.update_item(conn, workspaceId, batch_id, item_id, patch)
    return batch_out(conn, workspaceId, result)


@router.delete("/{batch_id}/items/{item_id}", response_model=BatchOut)
def remove_item(
    batch_id: str,
    item_id: str,
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    result = rules.remove_item(conn, workspaceId, batch_id, item_id)
    return batch_out(conn, workspaceId, result)


@router.post("/{batch_id}/items/reorder", response_model=BatchOut)
def reorder_items(
    batch_id: str,
    payload: ReorderIn,
    workspaceId: str = Query(..., alias="workspaceId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    result = rules.reorder_items(conn, workspaceId, batch_id, payload.orderedIds)
    return batch_out(conn, workspaceId, result)
