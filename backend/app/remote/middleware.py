"""Protege API, publica eventos confirmados e dá idempotência às escritas."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..db.connection import connect
from ..domain.utils import new_id, utc_now
from . import auth, events
from .state import remote_active

PUBLIC = {'/api/remote/status', '/api/remote/login'}
WRITE = {'POST', 'PUT', 'PATCH', 'DELETE'}
LOCAL_ONLY = {
    '/api/queue/opencode/config',
    '/api/remote/enable',
    '/api/remote/disable',
    '/api/remote/sessions',
}


def _workspace_from(request: Request) -> str:
    params = request.scope.get('path_params') or {}
    for key in ('workspace_id', 'workspaceId'):
        if params.get(key):
            return str(params[key])
    query = request.query_params.get('workspaceId') or ''
    if query:
        return query
    path = request.url.path
    part = path.split('/workspaces/')
    if len(part) > 1:
        return part[1].split('/')[0]
    return ''


def _event_type(path: str) -> str:
    if '/messages' in path or '/chat/' in path:
        return 'chat.message.changed'
    if '/queue/' in path:
        return 'queue.state.changed'
    if '/assistant/' in path:
        return 'assistant.state.changed'
    if '/delivery/' in path:
        return 'delivery.state.changed'
    return 'workspace.state.changed'


class RemoteGuard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith('/api/') or path in PUBLIC:
            return await call_next(request)

        conn = connect()
        try:
            if remote_active():
                token = request.cookies.get(auth.COOKIE, '')
                session = auth.get_session(conn, token)
                if session is None:
                    return JSONResponse(
                        status_code=401,
                        content={'code': 'UNAUTHENTICATED', 'message': 'Sessão ausente, expirada ou revogada.'},
                    )
                if not auth.csrf_valid(request, session):
                    return JSONResponse(
                        status_code=403,
                        content={'code': 'CSRF_INVALID', 'message': 'Token CSRF ausente ou inválido.'},
                    )
                if path in LOCAL_ONLY and request.method in WRITE:
                    return JSONResponse(
                        status_code=403,
                        content={'code': 'LOCAL_ONLY', 'message': 'Operação permitida somente no PC.'},
                    )
                request.state.user = session.get('user_label', 'remoto')
            else:
                request.state.user = 'local'

            key = request.headers.get('idempotency-key', '') if request.method in WRITE else ''
            if key:
                row = conn.execute(
                    'SELECT status, body FROM remote_operations WHERE request_key = ?', (key,)
                ).fetchone()
                if row:
                    return Response(
                        content=row['body'], status_code=row['status'],
                        media_type='application/json',
                        headers={'X-Idempotent-Replay': '1'},
                    )

            response = await call_next(request)
            body = b''
            if getattr(response, 'body_iterator', None) is not None:
                body = b''.join([chunk async for chunk in response.body_iterator])
                response = Response(
                    content=body, status_code=response.status_code,
                    headers=dict(response.headers), media_type=response.media_type,
                )

            if key and response.status_code < 400:
                with conn:
                    conn.execute(
                        'INSERT OR IGNORE INTO remote_operations '
                        '(request_key, method, path, status, body, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                        (key[:200], request.method, path[:300], response.status_code,
                         body.decode('utf-8', errors='replace')[:100_000], utc_now()),
                    )

            if response.status_code < 400 and request.method in WRITE:
                workspace_id = _workspace_from(request)
                if workspace_id:
                    try:
                        events.publish(
                            conn, workspace_id, _event_type(path),
                            {'path': path[:200], 'method': request.method}, 'alteração confirmada',
                        )
                    except Exception:
                        pass
            try:
                with conn:
                    conn.execute(
                        'INSERT INTO remote_audit (id, created_at, user_label, workspace_id, action, status, request_key) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (new_id('audit'), utc_now(), str(request.state.user),
                         _workspace_from(request), f'{request.method} {path[:200]}', response.status_code, key[:200]),
                    )
            except Exception:
                pass  # auditoria nunca deve derrubar a resposta já confirmada
            return response
        finally:
            conn.close()
