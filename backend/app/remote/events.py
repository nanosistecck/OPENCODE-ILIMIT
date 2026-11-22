"""Eventos com sequência atribuída pelo backend e replay por workspace."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..domain.utils import utc_now


def publish(
    conn: sqlite3.Connection,
    workspace_id: str,
    event_type: str,
    context: dict[str, Any] | None = None,
    summary: str = '',
) -> int:
    with conn:
        cursor = conn.execute(
            'INSERT INTO app_events (workspace_id, type, context, summary, created_at) '
            'VALUES (?, ?, ?, ?, ?)',
            (workspace_id, event_type, json.dumps(context or {}, ensure_ascii=False), summary, utc_now()),
        )
    return int(cursor.lastrowid)


def latest_sequence(conn: sqlite3.Connection, workspace_id: str) -> int:
    row = conn.execute(
        'SELECT MAX(sequence) AS seq FROM app_events WHERE workspace_id = ?', (workspace_id,)
    ).fetchone()
    return int(row['seq'] or 0)


def events_after(
    conn: sqlite3.Connection, workspace_id: str, after: int, limit: int = 200
) -> list[dict[str, Any]]:
    rows = conn.execute(
        'SELECT sequence, type, context, summary, created_at FROM app_events '
        'WHERE workspace_id = ? AND sequence > ? ORDER BY sequence LIMIT ?',
        (workspace_id, after, limit),
    ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        try:
            data['context'] = json.loads(data['context'] or '{}')
        except json.JSONDecodeError:
            data['context'] = {}
        result.append(data)
    return result


def has_gap(conn: sqlite3.Connection, workspace_id: str, after: int) -> bool:
    """Intervalo indisponível (limpeza/retenção) exige estado completo."""
    if after <= 0:
        return False
    row = conn.execute(
        'SELECT MIN(sequence) AS seq FROM app_events WHERE workspace_id = ?', (workspace_id,)
    ).fetchone()
    first = row['seq']
    return first is not None and after + 1 < int(first)
