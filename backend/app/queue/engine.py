"""Motor da fila: uma execução ativa por workspace, com verificação Git por tentativa."""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..config import settings
from ..db.connection import connect
from ..domain.errors import DomainError
from ..domain.utils import utc_now
from ..git import service as git_service
from ..opencode.client import OpenCodeClient
from . import persistence as store

REASON_LABELS = {
    'MISSING_PATH': 'Pasta de trabalho ausente.',
    'INVALID_REPOSITORY': 'A pasta não é um repositório Git válido.',
    'WRONG_REPOSITORY': 'A pasta pertence a outro repositório.',
    'BRANCH_CHANGED': 'A branch foi trocada externamente.',
    'DETACHED_HEAD': 'HEAD destacado na worktree.',
    'CONFLICTS': 'Existem conflitos na worktree.',
    'OPERATION_IN_PROGRESS': 'Há merge/rebase em andamento.',
    'LINK_PENDING': 'O vínculo Git ainda não foi confirmado.',
}


@contextmanager
def db() -> Iterator[Any]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class QueueEngine:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._processes: dict[str, Any] = {}

    def _lock(self, workspace_id: str) -> asyncio.Lock:
        return self._locks.setdefault(workspace_id, asyncio.Lock())

    def _client(self, conn: Any) -> OpenCodeClient:
        return OpenCodeClient(store.get_settings(conn)['executable'])

    def is_running(self, workspace_id: str) -> bool:
        return any(not task.done() for task in self._tasks.values()) and workspace_id in self._locks

    async def start(self, batch_id: str, resume_from: int = 0) -> dict[str, Any]:
        with db() as conn:
            workspace_id = store.batch_workspace(conn, batch_id)
            batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
            if batch['status'] not in ('idle', 'completed', 'failed', 'cancelled', 'interrupted', 'paused'):
                raise DomainError('Lote já está em execução.', code='ALREADY_RUNNING')
        lock = self._lock(workspace_id)
        if lock.locked():
            raise DomainError('Já existe uma execução ativa neste espaço.', code='WORKSPACE_BUSY')
        async with lock:
            with db() as conn:
                store.set_batch(
                    conn, batch_id,
                    status='running', cursor=resume_from, pause_requested=False,
                    cancel_requested=False, block_reason='', last_error='',
                )
            task = asyncio.create_task(self._run(batch_id, workspace_id), name=f'queue-{batch_id}')
            self._tasks[batch_id] = task
        return self.state(batch_id)

    async def pause(self, batch_id: str) -> dict[str, Any]:
        with db() as conn:
            workspace_id = store.batch_workspace(conn, batch_id)
            batch = conn.execute('SELECT status FROM batches WHERE id = ?', (batch_id,)).fetchone()
            if batch['status'] not in ('running', 'pausing'):
                raise DomainError('Só é possível pausar durante a execução.', code='INVALID_STATE')
            store.set_batch(conn, batch_id, status='pausing', pause_requested=True)
        return self.state(batch_id, workspace_id)

    async def resume(self, batch_id: str) -> dict[str, Any]:
        with db() as conn:
            workspace_id = store.batch_workspace(conn, batch_id)
            batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
            cursor = int(batch['cursor'])
        if self._lock(workspace_id).locked():
            raise DomainError('Espaço ocupado por outra execução.', code='WORKSPACE_BUSY')
        with db() as conn:
            store.set_batch(conn, batch_id, status='idle', pause_requested=False, block_reason='')
        return await self.start(batch_id, resume_from=cursor)

    async def cancel(self, batch_id: str) -> dict[str, Any]:
        with db() as conn:
            workspace_id = store.batch_workspace(conn, batch_id)
            batch = conn.execute('SELECT status, current_attempt_id FROM batches WHERE id = ?', (batch_id,)).fetchone()
            if batch['status'] not in ('running', 'pausing'):
                raise DomainError('Lote não está em execução.', code='INVALID_STATE')
            store.set_batch(conn, batch_id, status='cancelled', cancel_requested=True)
            attempt_id = batch['current_attempt_id']
            if attempt_id:
                store.update_attempt(conn, attempt_id, cancel_requested=True)
        process = self._processes.get(attempt_id or '')
        if process is not None:
            from ..opencode.client import terminate

            await terminate(process)
        return self.state(batch_id, workspace_id)

    async def retry(self, attempt_id: str, continue_session: bool = False) -> dict[str, Any]:
        with db() as conn:
            row = conn.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,)).fetchone()
            if row is None:
                raise DomainError('Tentativa não encontrada.', code='NOT_FOUND')
            if row['status'] not in ('failure', 'inconclusive', 'interrupted', 'cancelled'):
                raise DomainError('Esta tentativa não pode ser repetida.', code='INVALID_STATE')
            batch_id = row['batch_id']
            workspace_id = row['workspace_id']
            item_row = conn.execute('SELECT * FROM batch_items WHERE id = ?', (row['item_id'],)).fetchone()
            if item_row is None:
                raise DomainError('Item da tentativa não existe mais.', code='NOT_FOUND')
            if continue_session and not row['session_id']:
                raise DomainError('Esta tentativa não possui sessão para continuar.', code='NO_SESSION')
            session_id = row['session_id'] if continue_session else ''
            with conn:
                conn.execute(
                    "UPDATE batch_items SET status = 'pending' WHERE id = ?", (item_row['id'],)
                )
                conn.execute(
                    'UPDATE batches SET status = ?, block_reason = NULL, last_error = NULL, cursor = ?, '
                    'current_attempt_id = NULL WHERE id = ?',
                    ('idle', item_row['item_order'], batch_id),
                )
                conn.execute(
                    'UPDATE batches SET resume_session = ?, resume_of = ? WHERE id = ?',
                    (session_id or None, attempt_id, batch_id),
                )
        # O worker criará uma NOVA tentativa com o prompt original preservado.
        # session_id é usado apenas quando o usuário pediu "continuar sessão".
        return await self.start(batch_id, resume_from=int(item_row['item_order']))

    async def _run(self, batch_id: str, workspace_id: str) -> None:
        try:
            with db() as conn:
                config = store.get_settings(conn)
                client = OpenCodeClient(config['executable'])
                timeout = int(config['timeout'] or settings.opencode_timeout)

            while True:
                with db() as conn:
                    batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
                    if batch is None or batch['cancel_requested']:
                        break
                    items = conn.execute(
                        'SELECT * FROM batch_items WHERE batch_id = ? ORDER BY item_order', (batch_id,)
                    ).fetchall()
                    cursor = int(batch['cursor'])
                    if cursor >= len(items):
                        store.set_batch(conn, batch_id, status='completed', current_attempt_id='')
                        break
                    item = dict(items[cursor])
                    verification = git_service.verify(conn, workspace_id)

                if not verification['ready']:
                    reason = ', '.join(REASON_LABELS.get(code, code) for code in verification['reasons'])
                    with db() as conn:
                        store.set_batch(
                            conn, batch_id, status='paused', block_reason=reason or 'VERIFICATION_FAILED'
                        )
                    break

                depends_on = json.loads(item.get('depends_on') or '[]')
                with db() as conn:
                    done_ids = {
                        row['id'] for row in conn.execute(
                            "SELECT id FROM batch_items WHERE batch_id = ? AND status = 'done'", (batch_id,)
                        )
                    }
                missing = [dep for dep in depends_on if dep not in done_ids]
                if missing:
                    with db() as conn:
                        store.set_batch(conn, batch_id, status='paused', block_reason='DEPENDENCY_PENDING')
                    break

                prompt = item['content']
                OpenCodeClient.validate_prompt(prompt)
                resume_session = batch['resume_session'] if 'resume_session' in batch.keys() else ''
                resume_of = batch['resume_of'] if 'resume_of' in batch.keys() else ''
                with db() as conn:
                    attempt = store.create_attempt(
                        conn,
                        batch_id=batch_id,
                        item=item,
                        workspace_id=workspace_id,
                        prompt=prompt,
                        branch=verification['branch'],
                        work_dir=verification['path'],
                        head=verification['head'],
                        git_status=verification['localChanges'],
                        requested_model=config['model'],
                        requested_agent=config['agent'],
                        session_id=resume_session or '',
                        resume_of=resume_of or '',
                    )
                    conn.execute(
                        "UPDATE batch_items SET status = 'running' WHERE id = ?", (item['id'],)
                    )
                    conn.execute(
                        'UPDATE batches SET resume_session = NULL, resume_of = NULL WHERE id = ?',
                        (batch_id,),
                    )
                attempt_id = attempt['id']
                log_path = Path(attempt['log_path'])

                async def on_line(text: str) -> None:
                    with log_path.open('a', encoding='utf-8') as handle:
                        handle.write(text)

                process_holder: dict[str, Any] = {}
                result = await client.run(
                    prompt, verification['path'],
                    session_id=resume_session or '',
                    model=config['model'], agent=config['agent'],
                    on_line=on_line, timeout=timeout,
                    process_holder=process_holder,
                )
                if process_holder.get('process'):
                    self._processes[attempt_id] = process_holder['process']
                self._processes.pop(attempt_id, None)

                with db() as conn:
                    final_verification = git_service.verify(conn, workspace_id)
                    item_status = 'done' if result.status == 'success' else 'failed'
                    if result.status == 'cancelled':
                        item_status = 'pending'
                    store.update_attempt(
                        conn, attempt_id,
                        status=result.status,
                        result=result.final_text[:4000],
                        error=result.error[:4000],
                        finished_at=utc_now(),
                        session_id=result.session_id or attempt.get('session_id') or '',
                        exit_code=result.exit_code,
                        pid=process_holder.get('pid'),
                        events=result.events,
                        head_after=final_verification.get('head', ''),
                        git_status_after=final_verification.get('localChanges', {}),
                    )
                    conn.execute(
                        'UPDATE batch_items SET status = ? WHERE id = ?', (item_status, item['id'])
                    )
                    batch_now = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
                    pause_requested = bool(batch_now['pause_requested'])
                    cancelled = bool(batch_now['cancel_requested'])
                    if cancelled:
                        store.set_batch(
                            conn, batch_id, status='cancelled', pause_requested=False,
                            cancel_requested=False, current_attempt_id='',
                        )
                    elif pause_requested:
                        store.set_batch(
                            conn, batch_id, status='paused', pause_requested=False,
                            current_attempt_id='',
                        )
                    elif result.status != 'success':
                        store.set_batch(
                            conn, batch_id, status='failed', last_error=result.error[:4000],
                            current_attempt_id='',
                        )
                    else:
                        store.set_batch(
                            conn, batch_id, status='running', cursor=cursor + 1,
                            current_attempt_id='',
                        )

                if cancelled or pause_requested or result.status != 'success':
                    break

        except Exception as exc:  # falha inesperada do motor
            with db() as conn:
                store.set_batch(
                    conn, batch_id, status='failed', last_error=str(exc)[:4000],
                    current_attempt_id='',
                )
        finally:
            self._tasks.pop(batch_id, None)

    def state(self, batch_id: str, workspace_id: str = '') -> dict[str, Any]:
        with db() as conn:
            workspace_id = workspace_id or store.batch_workspace(conn, batch_id)
            return store.batch_state(conn, workspace_id, batch_id)


engine = QueueEngine()
