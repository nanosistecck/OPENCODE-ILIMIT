"""Sessões locais/remotas com cookie seguro, CSRF e logout/revogação."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request

from ..config import settings
from ..domain.utils import new_id, utc_now

COOKIE = 'ocilimit_session'


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(conn: sqlite3.Connection, user_label: str = 'remoto') -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(hours=settings.remote_session_hours)).isoformat()
    with conn:
        conn.execute(
            'INSERT INTO remote_sessions (token_hash, user_label, created_at, expires_at, csrf) '
            'VALUES (?, ?, ?, ?, ?)',
            (hash_token(token), user_label or 'remoto', utc_now(), expires, csrf),
        )
    return {'token': token, 'csrf': csrf, 'expiresAt': expires}


def get_session(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    if not token:
        return None
    row = conn.execute(
        'SELECT * FROM remote_sessions WHERE token_hash = ?', (hash_token(token),)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    if data.get('revoked_at'):
        return None
    try:
        if datetime.fromisoformat(data['expires_at']) <= datetime.now(timezone.utc):
            return None
    except (ValueError, KeyError):
        return None
    with conn:
        conn.execute('UPDATE remote_sessions SET last_seen_at = ? WHERE token_hash = ?',
                     (utc_now(), hash_token(token)))
    return data


def revoke_session(conn: sqlite3.Connection, token: str) -> None:
    with conn:
        conn.execute('UPDATE remote_sessions SET revoked_at = ? WHERE token_hash = ?',
                     (utc_now(), hash_token(token)))


def revoke_all(conn: sqlite3.Connection) -> int:
    with conn:
        cursor = conn.execute('UPDATE remote_sessions SET revoked_at = ? WHERE revoked_at IS NULL',
                              (utc_now(),))
    return cursor.rowcount


def check_password(password: str) -> bool:
    expected = settings.remote_password
    if not expected:
        return False
    return hmac.compare_digest(password or '', expected)


def identity_hint(request: Request) -> str:
    """Cabeçalho de identidade do túnel é SUGESTÃO, não prova verificada."""
    return (request.headers.get(settings.remote_identity_header) or '').strip()[:120]


def csrf_valid(request: Request, session: dict[str, Any]) -> bool:
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return True
    supplied = request.headers.get('x-csrf-token') or ''
    return bool(supplied) and hmac.compare_digest(supplied, session.get('csrf', ''))
