"""Conversas e mensagens vinculadas a um espaço."""

from __future__ import annotations

import sqlite3
from typing import Any

from .errors import NotFoundError
from .projects import get_workspace
from .utils import new_id, utc_now


def ensure_conversation(conn: sqlite3.Connection, workspace_id: str, title: str = "Conversa") -> dict[str, Any]:
    get_workspace(conn, workspace_id)
    row = conn.execute(
        "SELECT * FROM conversations WHERE workspace_id = ? ORDER BY created_at LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if row is not None:
        return dict(row)
    conversation_id = new_id("conv")
    conn.execute(
        "INSERT INTO conversations (id, workspace_id, title, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, workspace_id, title or "Conversa", utc_now()),
    )
    return get_conversation(conn, workspace_id, conversation_id)


def create_conversation(conn: sqlite3.Connection, workspace_id: str, title: str = "Conversa") -> dict[str, Any]:
    get_workspace(conn, workspace_id)
    conversation_id = new_id("conv")
    conn.execute(
        "INSERT INTO conversations (id, workspace_id, title, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, workspace_id, title or "Conversa", utc_now()),
    )
    return get_conversation(conn, workspace_id, conversation_id)


def get_conversation(conn: sqlite3.Connection, workspace_id: str, conversation_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND workspace_id = ?",
        (conversation_id, workspace_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("Conversa não pertence a este espaço.")
    return dict(row)


def list_conversations(conn: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    get_workspace(conn, workspace_id)
    return [dict(row) for row in conn.execute(
        "SELECT * FROM conversations WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)
    )]


def list_messages(conn: sqlite3.Connection, workspace_id: str, conversation_id: str) -> list[dict[str, Any]]:
    get_conversation(conn, workspace_id, conversation_id)
    return [dict(row) for row in conn.execute(
        "SELECT * FROM messages WHERE workspace_id = ? AND conversation_id = ? "
        "ORDER BY position, created_at",
        (workspace_id, conversation_id),
    )]


def add_message(
    conn: sqlite3.Connection,
    workspace_id: str,
    conversation_id: str,
    role: str,
    content: str,
    status: str = "sent",
) -> dict[str, Any]:
    get_conversation(conn, workspace_id, conversation_id)
    text = (content or "").strip()
    if not text:
        raise ValueError("Mensagem vazia")
    next_position = conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()[0]
    message_id = new_id("msg")
    conn.execute(
        "INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (message_id, conversation_id, workspace_id, role, text, next_position, status, utc_now()),
    )
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return dict(row)
