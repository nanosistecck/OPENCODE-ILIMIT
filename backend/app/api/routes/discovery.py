"""Descoberta e abertura de projetos Git."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ...discovery import service
from ...domain.errors import DomainError
from ...domain.utils import utc_now
from ...remote.state import remote_active
from ..deps import get_db
from ..schemas import DiscoveryOpenIn, DiscoveryPathIn, DiscoveryPreferencesIn

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _local_only() -> None:
    if remote_active():
        raise DomainError(
            'Informar pastas do Windows é uma operação local. Abra o projeto no PC.',
            code='LOCAL_ONLY', status=403,
        )


@router.post('/preview')
def preview(payload: DiscoveryPathIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    _local_only()
    return service.preview(conn, payload.path, payload.github)


@router.post('/open')
def open_project(payload: DiscoveryOpenIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    _local_only()
    return service.open_project(conn, payload.path, payload.choices)


@router.get('/preferences')
def get_preferences(
    projectId: str = Query(..., alias='projectId'),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return service.preferences(conn, projectId)


@router.put('/preferences')
def put_preferences(
    payload: DiscoveryPreferencesIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    with conn:
        conn.execute(
            'INSERT INTO project_discovery_preferences (project_id, base_branch, publish_remote, '
            'pr_repository, pr_base, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(project_id) DO UPDATE SET base_branch = excluded.base_branch, '
            'publish_remote = excluded.publish_remote, pr_repository = excluded.pr_repository, '
            'pr_base = excluded.pr_base, updated_at = excluded.updated_at, updated_by = excluded.updated_by',
            (payload.projectId, payload.baseBranch, payload.publishRemote,
             payload.prRepository, payload.prBase, utc_now(), 'usuario'),
        )
    return service.preferences(conn, payload.projectId)


@router.get('/worktrees')
def worktrees(
    workspaceId: str = Query(..., alias='workspaceId'),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute('SELECT git_repo_root, git_common_dir FROM workspaces WHERE id = ?',
                       (workspaceId,)).fetchone()
    if row is None:
        raise DomainError('Espaço não encontrado.', code='NOT_FOUND')
    from ...git import local as git_local

    items = []
    root = row['git_repo_root'] or ''
    if root:
        items = git_local.list_worktrees(root)
    return {'workspaceId': workspaceId, 'worktrees': items}
