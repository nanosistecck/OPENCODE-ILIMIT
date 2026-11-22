"""Rotas de sessão, eventos HTTP e WebSocket."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from ..config import settings
from ..db.connection import connect, get_db
from . import auth, events
from .state import remote_active, set_remote_active

router = APIRouter(tags=['remote'])


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return True  # clientes sem Origin (testes/HTTP locais)
    allowed = set(settings.remote_allowed_origins)
    if settings.remote_public_origin:
        allowed.add(settings.remote_public_origin)
    allowed.update({'http://localhost:5173', 'http://127.0.0.1:5173'})
    return origin in allowed


@router.get('/api/remote/status')
def status(request: Request) -> dict[str, Any]:
    conn = connect()
    try:
        token = request.cookies.get(auth.COOKIE, '')
        session = auth.get_session(conn, token)
        return {
            'enabled': settings.remote_enabled,
            'active': remote_active(),
            'authenticated': session is not None,
            'user': session.get('user_label', '') if session else '',
            'csrf': session.get('csrf', '') if session else '',
            'expiresAt': session.get('expires_at', '') if session else '',
            'publicOrigin': settings.remote_public_origin,
            'provider': settings.remote_provider,
            'identityHeader': settings.remote_identity_header,
            'note': 'Cabeçalhos de identidade do túnel são sugestão até validação no provedor.',
        }
    finally:
        conn.close()


@router.post('/api/remote/login')
def login(payload: dict[str, Any], request: Request) -> JSONResponse:
    conn = connect()
    try:
        if not remote_active():
            return JSONResponse(status_code=403, content={'code': 'REMOTE_DISABLED', 'message': 'Acesso remoto desativado.'})
        if not auth.check_password(str(payload.get('password') or '')):
            return JSONResponse(status_code=401, content={'code': 'BAD_PASSWORD', 'message': 'Senha inválida.'})
        label = auth.identity_hint(request) or 'remoto'
        session = auth.create_session(conn, label)
        response = JSONResponse(content={'ok': True, 'csrf': session['csrf'], 'expiresAt': session['expiresAt']})
        response.set_cookie(
            auth.COOKIE, session['token'], httponly=True, samesite='strict',
            secure=bool(settings.remote_public_origin.startswith('https://')),
            max_age=settings.remote_session_hours * 3600, path='/',
        )
        return response
    finally:
        conn.close()


@router.post('/api/remote/logout')
def logout(request: Request) -> JSONResponse:
    conn = connect()
    try:
        token = request.cookies.get(auth.COOKIE, '')
        auth.revoke_session(conn, token)
        response = JSONResponse(content={'ok': True})
        response.delete_cookie(auth.COOKIE, path='/')
        return response
    finally:
        conn.close()


@router.get('/api/remote/sessions')
def sessions(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    rows = conn.execute(
        'SELECT user_label, created_at, expires_at, revoked_at, last_seen_at FROM remote_sessions '
        'ORDER BY created_at DESC LIMIT 50'
    ).fetchall()
    return {'sessions': [dict(row) for row in rows]}


@router.post('/api/remote/disable')
def disable(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    set_remote_active(False)
    count = auth.revoke_all(conn)
    return {'active': False, 'revoked': count}


@router.post('/api/remote/enable')
def enable() -> dict[str, Any]:
    set_remote_active(True)
    return {'active': True}


@router.get('/api/events')
def http_events(
    workspaceId: str = Query(..., alias='workspaceId'),
    after: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    sequence = events.latest_sequence(conn, workspaceId)
    gap = events.has_gap(conn, workspaceId, after)
    return {
        'workspaceId': workspaceId,
        'sequence': sequence,
        'events': [] if gap else events.events_after(conn, workspaceId, after),
        'resync': gap,
    }


@router.websocket('/ws/events')
async def ws_events(websocket: WebSocket) -> None:
    origin = websocket.headers.get('origin', '')
    if not _origin_allowed(origin):
        await websocket.close(code=4403)
        return
    conn = connect()
    try:
        if remote_active():
            session = auth.get_session(conn, websocket.cookies.get(auth.COOKIE, ''))
            if session is None:
                await websocket.close(code=4401)
                return
        workspace_id = websocket.query_params.get('workspaceId', '')
        if not workspace_id:
            await websocket.close(code=4400)
            return
        after = int(websocket.query_params.get('after', '0') or 0)
        await websocket.accept()
        last = events.latest_sequence(conn, workspace_id)
        await websocket.send_json({
            'type': 'snapshot', 'workspaceId': workspace_id,
            'sequence': last, 'after': after,
            'resync': events.has_gap(conn, workspace_id, after),
        })
        while True:
            pending = events.events_after(conn, workspace_id, last)
            for event in pending:
                await websocket.send_json(event)
                last = max(last, int(event['sequence']))
            if events.has_gap(conn, workspace_id, last):
                await websocket.send_json({
                    'type': 'resync', 'workspaceId': workspace_id,
                    'sequence': events.latest_sequence(conn, workspace_id),
                })
                last = events.latest_sequence(conn, workspace_id)
            await asyncio.sleep(0.4)
    except (WebSocketDisconnect, RuntimeError, OSError):
        return
    finally:
        conn.close()
