"""Lotes e itens de fila. Reordenacao exige o conjunto exato de IDs esperados."""

from __future__ import annotations

import sqlite3
from typing import Any

from .errors import DomainError, NotFoundError
from .projects import get_workspace
from .utils import new_id, utc_now


def get_batch(conn: sqlite3.Connection, workspace_id: str, batch_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM batches WHERE id = ? AND workspace_id = ?", (batch_id, workspace_id)
    ).fetchone()
    if row is None:
        raise NotFoundError("Lote não pertence a este espaço.")
    return dict(row)


def list_batches(conn: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    get_workspace(conn, workspace_id)
    return [dict(row) for row in conn.execute(
        "SELECT * FROM batches WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,)
    )]


def _insert_batch(conn: sqlite3.Connection, workspace_id: str, name: str, source_version_id: str | None = None) -> dict[str, Any]:
    batch_id = new_id("batch")
    now = utc_now()
    conn.execute(
        "INSERT INTO batches (id, workspace_id, name, source_version_id, status, cursor, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'idle', 0, ?, ?)",
        (batch_id, workspace_id, name, source_version_id, now, now),
    )
    return get_batch(conn, workspace_id, batch_id)


def create_batch(conn: sqlite3.Connection, workspace_id: str, name: str) -> dict[str, Any]:
    get_workspace(conn, workspace_id)
    with conn:
        return _insert_batch(conn, workspace_id, (name or "Lote manual").strip())


def create_batch_from_version(
    conn: sqlite3.Connection, workspace_id: str, version: dict[str, Any]
) -> dict[str, Any]:
    """Copia os prompts em ordem e registra a origem — tudo em uma transação."""
    now = utc_now()
    with conn:
        batch = _insert_batch(
            conn, workspace_id, f"Fila do plano v{version['version']}", version["id"]
        )
        for index, step in enumerate(version["steps"]):
            conn.execute(
                "INSERT INTO batch_items (id, batch_id, item_order, kind, title, content, file_name, "
                "status, created_at, depends_on, acceptance_criteria) "
                "VALUES (?, ?, ?, 'prompt', ?, ?, NULL, 'pending', ?, ?, ?)",
                (
                    new_id("item"),
                    batch["id"],
                    index,
                    step.get("title") or f"Etapa {index + 1}",
                    step.get("prompt") or step.get("description") or "",
                    now,
                    __import__("json").dumps(step.get("dependencies") or [], ensure_ascii=False),
                    step.get("acceptanceCriteria") or "",
                ),
            )
    return batch_with_items(conn, workspace_id, batch["id"])


def batch_with_items(conn: sqlite3.Connection, workspace_id: str, batch_id: str) -> dict[str, Any]:
    batch = get_batch(conn, workspace_id, batch_id)
    batch["items"] = [
        _item_out(row) for row in conn.execute(
            "SELECT * FROM batch_items WHERE batch_id = ? ORDER BY item_order", (batch_id,)
        )
    ]
    return batch


def _item_out(row: sqlite3.Row) -> dict[str, Any]:
    import json

    item = dict(row)
    item["order"] = item.pop("item_order")
    item["fileName"] = item.pop("file_name")
    item["dependsOn"] = json.loads(item.pop("depends_on", "[]") or "[]")
    item["acceptanceCriteria"] = item.pop("acceptance_criteria", "")
    return item


def list_batches_with_items(conn: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    return [batch_with_items(conn, workspace_id, batch["id"]) for batch in list_batches(conn, workspace_id)]


def _require_pending_item(conn: sqlite3.Connection, batch_id: str, item_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM batch_items WHERE id = ? AND batch_id = ?", (item_id, batch_id)
    ).fetchone()
    if row is None:
        raise NotFoundError("Item não encontrado.")
    if row["status"] != "pending":
        raise DomainError("Somente itens pendentes podem ser alterados.", code="ITEM_NOT_PENDING")
    return row


def add_items(conn: sqlite3.Connection, workspace_id: str, batch_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    get_batch(conn, workspace_id, batch_id)
    if not items:
        raise DomainError("Nenhum item informado.", code="VALIDATION", status=422)
    now = utc_now()
    with conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(item_order), -1) + 1 FROM batch_items WHERE batch_id = ?", (batch_id,)
        ).fetchone()[0]
        for offset, item in enumerate(items):
            content = item.get("content") or ""
            if not content.strip():
                raise DomainError("Conteúdo do prompt não pode ser vazio.", code="VALIDATION", status=422)
            conn.execute(
                "INSERT INTO batch_items (id, batch_id, item_order, kind, title, content, file_name, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (
                    new_id("item"),
                    batch_id,
                    next_order + offset,
                    item.get("kind") or "prompt",
                    item.get("title") or "Prompt",
                    content,
                    item.get("fileName"),
                    now,
                ),
            )
        conn.execute("UPDATE batches SET updated_at = ? WHERE id = ?", (now, batch_id))
    return batch_with_items(conn, workspace_id, batch_id)


def update_item(
    conn: sqlite3.Connection, workspace_id: str, batch_id: str, item_id: str, patch: dict[str, Any]
) -> dict[str, Any]:
    get_batch(conn, workspace_id, batch_id)
    with conn:
        _require_pending_item(conn, batch_id, item_id)
        updates: dict[str, Any] = {}
        if "title" in patch:
            updates["title"] = patch["title"] or "Prompt"
        if "content" in patch:
            if not (patch["content"] or "").strip():
                raise DomainError("Conteúdo do prompt não pode ser vazio.", code="VALIDATION", status=422)
            updates["content"] = patch["content"]
        if "fileName" in patch:
            updates["file_name"] = patch["fileName"]
        if updates:
            columns = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(f"UPDATE batch_items SET {columns} WHERE id = ?", (*updates.values(), item_id))
        conn.execute("UPDATE batches SET updated_at = ? WHERE id = ?", (utc_now(), batch_id))
    return batch_with_items(conn, workspace_id, batch_id)


def remove_item(conn: sqlite3.Connection, workspace_id: str, batch_id: str, item_id: str) -> dict[str, Any]:
    get_batch(conn, workspace_id, batch_id)
    with conn:
        _require_pending_item(conn, batch_id, item_id)
        conn.execute("DELETE FROM batch_items WHERE id = ?", (item_id,))
        for index, row in enumerate(conn.execute(
            "SELECT id FROM batch_items WHERE batch_id = ? ORDER BY item_order", (batch_id,)
        )):
            conn.execute("UPDATE batch_items SET item_order = ? WHERE id = ?", (index, row["id"]))
        conn.execute("UPDATE batches SET updated_at = ? WHERE id = ?", (utc_now(), batch_id))
    return batch_with_items(conn, workspace_id, batch_id)


def reorder_items(
    conn: sqlite3.Connection, workspace_id: str, batch_id: str, ordered_ids: list[str]
) -> dict[str, Any]:
    get_batch(conn, workspace_id, batch_id)
    with conn:
        rows = list(conn.execute(
            "SELECT id, status FROM batch_items WHERE batch_id = ?", (batch_id,)
        ))
        current_ids = {row["id"] for row in rows}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != current_ids:
            raise DomainError("A nova ordem não contém exatamente os itens do lote.", code="INVALID_ORDER")
        if any(row["status"] != "pending" for row in rows):
            raise DomainError("Somente itens pendentes podem ser reordenados.", code="ITEM_NOT_PENDING")
        # Valores temporários negativos evitam colisão com a UNIQUE(batch_id, item_order).
        conn.execute(
            "UPDATE batch_items SET item_order = -item_order - 1 WHERE batch_id = ?", (batch_id,)
        )
        for index, item_id in enumerate(ordered_ids):
            conn.execute(
                "UPDATE batch_items SET item_order = ? WHERE id = ?", (index, item_id)
            )
        conn.execute("UPDATE batches SET updated_at = ? WHERE id = ?", (utc_now(), batch_id))
    return batch_with_items(conn, workspace_id, batch_id)
