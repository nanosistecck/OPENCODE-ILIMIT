"""Rotas de Git local. Toda resolução de caminho acontece no backend."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ...git import service
from ...domain.errors import DomainError
from ...remote.state import remote_active
from ..deps import get_db
from ..schemas import GitCreateIn, GitOpenIn, RepoProbeIn, RepoLinkIn

router = APIRouter(prefix="/git", tags=["git"])


@router.post("/probe")
def probe(payload: RepoProbeIn) -> dict:
    if remote_active():
        raise DomainError('Consultar caminhos do Windows é uma operação local.', code='LOCAL_ONLY')
    return service.probe_repository(payload.path)


@router.post("/projects/{project_id}/repository")
def link_repository(project_id: str, payload: RepoLinkIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    if remote_active():
        raise DomainError('Cadastrar caminhos do Windows é uma operação local.', code='LOCAL_ONLY')
    return service.link_repository(conn, project_id, payload.path)


@router.get("/projects/{project_id}/overview")
def overview(project_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.overview(conn, project_id)


@router.post("/workspaces/{workspace_id}/branches")
def create_branch(
    workspace_id: str, payload: GitCreateIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return service.create_branch_workspace(conn, workspace_id, payload.branch, payload.startRef)


@router.post("/workspaces/{workspace_id}/open")
def open_workspace(
    workspace_id: str, payload: GitOpenIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    if remote_active() and payload.action == 'link' and payload.path:
        raise DomainError(
            'Vincular caminhos arbitrários do Windows é uma operação local. '
            'Use "criar worktree para branch local" ou "a partir do remoto".',
            code='LOCAL_ONLY',
        )
    return service.open_workspace(
        conn, workspace_id, payload.action,
        path=payload.path, source_ref=payload.sourceRef, branch=payload.branch,
    )


@router.get("/workspaces/{workspace_id}/status")
def status(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.status_payload(conn, workspace_id)


@router.post("/workspaces/{workspace_id}/refresh")
def refresh(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.status_payload(conn, workspace_id)


@router.get("/workspaces/{workspace_id}/diff")
def diff(
    workspace_id: str,
    file: str = Query(..., alias="file"),
    staged: bool = False,
    untracked: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return service.diff_payload(conn, workspace_id, file, staged, untracked)


@router.post("/workspaces/{workspace_id}/verify")
def verify(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.verify(conn, workspace_id)
