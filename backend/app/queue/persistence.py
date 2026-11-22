"""Acesso SQLite das tentativas e do estado do motor."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ..config import settings
from ..domain.errors import DomainError, NotFoundError
from ..domain.utils import new_id, utc_now

DEFAULT_SETTINGS = {
    'executable': '',
    'model': '',
    'agent': '',
    'timeout': str(settings.opencode_timeout),
}


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    for row in conn.execute('SELECT key, value FROM app_settings'):
        values[row['key']] = row['value']
    return values


def update_settings(conn: sqlite3.Connection, patch: dict[str, Any]) -> dict[str, Any]:
    with conn:
        for key, value in patch.items():
            if key not in DEFAULT_SETTINGS or value is None:
                continue
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                (key, str(value)),
            )
    return get_settings(conn)


def attempt_out(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    events = data.pop('events', '[]')
    try:
        data['events'] = json.loads(events or '[]')
    except (TypeError, json.JSONDecodeError):
        data['events'] = []

    aliases = {
        'batchId': 'batch_id', 'itemId': 'item_id', 'workspaceId': 'workspace_id',
        'sessionId': 'session_id', 'promptSnapshot': 'prompt_snapshot',
        'createdAt': 'created_at', 'startedAt': 'started_at', 'finishedAt': 'finished_at',
        'logPath': 'log_path', 'headBefore': 'head_before', 'headAfter': 'head_after',
        'statusBefore': 'git_status_before', 'statusAfter': 'git_status_after',
        'requestedModel': 'requested_model', 'observedModel': 'observed_model',
        'requestedAgent': 'requested_agent', 'exitCode': 'exit_code',
        'resumeOf': 'resume_of', 'acceptanceCriteria': 'acceptance_criteria',
        'workDir': 'work_dir',
    }
    for camel, snake in aliases.items():
        data[camel] = data.get(snake)
    data['cancelRequested'] = bool(data.get('cancel_requested', 0))
    return data


def create_attempt(
    conn: sqlite3.Connection,
    *,
    batch_id: str,
    item: dict[str, Any],
    workspace_id: str,
    prompt: str,
    branch: str,
    work_dir: str,
    head: str,
    git_status: dict[str, Any],
    requested_model: str,
    requested_agent: str,
    session_id: str = '',
    resume_of: str = '',
) -> dict[str, Any]:
    attempt_id = new_id('attempt')
    log_path = settings.logs_dir / f'{attempt_id}.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('', encoding='utf-8')
    now = utc_now()
    with conn:
        conn.execute(
            'INSERT INTO attempts (id, batch_id, item_id, workspace_id, session_id, prompt_snapshot, '
            'created_at, started_at, status, result, error, log_path, pid, head_before, git_status_before, '
            'requested_model, requested_agent, acceptance_criteria, branch, work_dir, resume_of) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                attempt_id, batch_id, item['id'], workspace_id, session_id or None, prompt,
                now, now, 'running', '', '', str(log_path), None, head,
                json.dumps(git_status, ensure_ascii=False), requested_model or None,
                requested_agent or None, item.get('acceptanceCriteria') or '', branch, work_dir,
                resume_of or None,
            ),
        )
        conn.execute(
            'UPDATE batches SET current_attempt_id = ?, last_error = NULL, updated_at = ? WHERE id = ?',
            (attempt_id, now, batch_id),
        )
    return get_attempt(conn, attempt_id)


def get_attempt(conn: sqlite3.Connection, attempt_id: str) -> dict[str, Any]:
    row = conn.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,)).fetchone()
    if row is None:
        raise NotFoundError('Tentativa não encontrada.')
    return attempt_out(row)


def update_attempt(conn: sqlite3.Connection, attempt_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        'status', 'result', 'error', 'finished_at', 'pid', 'session_id', 'observed_model',
        'exit_code', 'events', 'head_after', 'git_status_after', 'cancel_requested',
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if 'events' in updates and not isinstance(updates['events'], str):
        updates['events'] = json.dumps(updates['events'], ensure_ascii=False)
    if 'git_status_after' in updates and not isinstance(updates['git_status_after'], str):
        updates['git_status_after'] = json.dumps(updates['git_status_after'], ensure_ascii=False)
    if updates:
        columns = ', '.join(f'{key} = ?' for key in updates)
        with conn:
            conn.execute(f'UPDATE attempts SET {columns} WHERE id = ?', (*updates.values(), attempt_id))
    return get_attempt(conn, attempt_id)


def list_attempts(conn: sqlite3.Connection, workspace_id: str, batch_id: str = '') -> list[dict[str, Any]]:
    query = 'SELECT * FROM attempts WHERE workspace_id = ?'
    params: list[Any] = [workspace_id]
    if batch_id:
        query += ' AND batch_id = ?'
        params.append(batch_id)
    query += ' ORDER BY created_at DESC'
    return [attempt_out(row) for row in conn.execute(query, params)]


def set_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    status: str | None = None,
    cursor: int | None = None,
    pause_requested: bool | None = None,
    cancel_requested: bool | None = None,
    block_reason: str | None = None,
    last_error: str | None = None,
    current_attempt_id: str | None = None,
    resume_session: str | None = None,
    resume_of: str | None = None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if status is not None:
        updates['status'] = status
    if cursor is not None:
        updates['cursor'] = cursor
    if pause_requested is not None:
        updates['pause_requested'] = int(pause_requested)
    if cancel_requested is not None:
        updates['cancel_requested'] = int(cancel_requested)
    if block_reason is not None:
        updates['block_reason'] = block_reason
    if last_error is not None:
        updates['last_error'] = last_error
    if current_attempt_id is not None:
        updates['current_attempt_id'] = current_attempt_id
    if resume_session is not None:
        updates['resume_session'] = resume_session
    if resume_of is not None:
        updates['resume_of'] = resume_of
    updates['updated_at'] = utc_now()
    columns = ', '.join(f'{key} = ?' for key in updates)
    with conn:
        conn.execute(f'UPDATE batches SET {columns} WHERE id = ?', (*updates.values(), batch_id))
    row = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
    if row is None:
        raise NotFoundError('Lote não encontrado.')
    return dict(row)


def batch_workspace(conn: sqlite3.Connection, batch_id: str) -> str:
    row = conn.execute('SELECT workspace_id FROM batches WHERE id = ?', (batch_id,)).fetchone()
    if row is None:
        raise NotFoundError('Lote não encontrado.')
    return str(row['workspace_id'])


def batch_state(conn: sqlite3.Connection, workspace_id: str, batch_id: str) -> dict[str, Any]:
    from ..domain.batches import get_batch

    batch = get_batch(conn, workspace_id, batch_id)
    items = [
        {
            'id': row['id'], 'order': row['item_order'], 'title': row['title'],
            'content': row['content'], 'kind': row['kind'], 'status': row['status'],
            'dependsOn': json.loads(row['depends_on'] or '[]'),
            'acceptanceCriteria': row['acceptance_criteria'] or '',
        }
        for row in conn.execute('SELECT * FROM batch_items WHERE batch_id = ? ORDER BY item_order', (batch_id,))
    ]
    return {
        'id': batch['id'],
        'workspaceId': workspace_id,
        'name': batch['name'],
        'status': batch['status'],
        'cursor': batch['cursor'],
        'pauseRequested': bool(batch['pause_requested']),
        'cancelRequested': bool(batch['cancel_requested']),
        'blockReason': batch.get('block_reason') or '',
        'lastError': batch.get('last_error') or '',
        'currentAttemptId': batch.get('current_attempt_id') or '',
        'items': items,
        'attempts': list_attempts(conn, workspace_id, batch_id),
    }


def read_log(attempt_id: str, offset: int = 0, limit: int = 16_000) -> dict[str, Any]:
    attempt_row = None
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        attempt_row = conn.execute('SELECT log_path FROM attempts WHERE id = ?', (attempt_id,)).fetchone()
    finally:
        conn.close()
    if attempt_row is None:
        raise NotFoundError('Tentativa não encontrada.')
    path = Path(attempt_row['log_path'])
    if not path.exists():
        return {'text': '', 'nextOffset': offset, 'done': True}
    raw = path.read_bytes()
    chunk = raw[offset:offset + limit]
    next_offset = offset + len(chunk)
    return {
        'text': chunk.decode('utf-8', errors='replace'),
        'nextOffset': next_offset,
        'done': next_offset >= len(raw),
    }


def recover_interrupted(conn: sqlite3.Connection) -> dict[str, Any]:
    """Marc execuções ativas como interrompidas: nunca repetir automaticamente."""
    rows = list(conn.execute("SELECT * FROM attempts WHERE status = 'running'"))
    recovered: list[str] = []
    blocked: list[str] = []
    for row in rows:
        alive = _process_alive(row['pid'])
        with conn:
            conn.execute(
                "UPDATE attempts SET status = 'interrupted', finished_at = ?, "
                "error = CASE WHEN ? = 1 THEN 'Processo anterior pode ainda estar ativo' "
                "ELSE 'Backend reiniciado durante a execução' END WHERE id = ?",
                (utc_now(), int(alive), row['id']),
            )
            conn.execute(
                "UPDATE batches SET status = 'interrupted', block_reason = ?, current_attempt_id = NULL, "
                "pause_requested = 0, cancel_requested = 0, updated_at = ? WHERE id = ?",
                ('PREVIOUS_PROCESS_ALIVE' if alive else 'ATTEMPT_INTERRUPTED', utc_now(), row['batch_id']),
            )
        (blocked if alive else recovered).append(row['id'])
    return {'interrupted': recovered + blocked, 'blocked': blocked}


def _process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if os.name == 'nt':
            import subprocess

            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                capture_output=True, text=True, timeout=8, check=False,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False
