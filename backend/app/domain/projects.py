"""Regras de projetos e espaços. Usadas por rotas e pelo futuro motor de execução."""

from __future__ import annotations

import sqlite3
from typing import Any

from .errors import DomainError, NotFoundError
from .utils import new_id, utc_now


def create_project(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise DomainError("Nome do projeto é obrigatório.", code="VALIDATION", status=422)
    base_branch = (data.get("baseBranch") or "main").strip() or "main"
    project_id = new_id("prj")
    now = utc_now()
    conn.execute(
        "INSERT INTO projects (id, name, objective, rules, base_branch, repo_path, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            name,
            data.get("objective") or "",
            data.get("rules") or "",
            base_branch,
            data.get("repoPath") or None,
            now,
            now,
        ),
    )
    return get_project(conn, project_id)


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY created_at, name")]


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise NotFoundError("Projeto não encontrado.")
    return dict(row)


def update_project(conn: sqlite3.Connection, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    get_project(conn, project_id)
    allowed = {"name", "objective", "rules", "base_branch", "repo_path"}
    updates = {key: value for key, value in patch.items() if key in allowed}
    if not updates:
        return get_project(conn, project_id)
    updates["updated_at"] = utc_now()
    columns = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(f"UPDATE projects SET {columns} WHERE id = ?", (*updates.values(), project_id))
    return get_project(conn, project_id)


def create_workspace(conn: sqlite3.Connection, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
    get_project(conn, project_id)
    name = (data.get("name") or "").strip()
    branch = (data.get("branch") or "").strip()
    if not name or not branch:
        raise DomainError("Nome e branch são obrigatórios.", code="VALIDATION", status=422)
    exists = conn.execute(
        "SELECT 1 FROM workspaces WHERE project_id = ? AND branch = ?", (project_id, branch)
    ).fetchone()
    if exists:
        raise DomainError("Já existe um espaço com esta branch no projeto.", code="DUPLICATE_BRANCH")
    project = get_project(conn, project_id)
    base_branch = (data.get("baseBranch") or project["base_branch"] or "main").strip() or "main"
    workspace_id = new_id("ws")
    now = utc_now()
    conn.execute(
        "INSERT INTO workspaces "
        "(id, project_id, name, branch, base_branch, work_dir, kind, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            workspace_id,
            project_id,
            name,
            branch,
            base_branch,
            data.get("workDir") or "",
            data.get("kind") or "worktree",
            now,
            now,
        ),
    )
    return get_workspace(conn, workspace_id)


def list_workspaces(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    get_project(conn, project_id)
    return [dict(row) for row in conn.execute(
        "SELECT * FROM workspaces WHERE project_id = ? ORDER BY created_at, name", (project_id,)
    )]


def get_workspace(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if row is None:
        raise NotFoundError("Espaço de trabalho não encontrado.")
    return dict(row)


def update_workspace(conn: sqlite3.Connection, workspace_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    get_workspace(conn, workspace_id)
    allowed = {"name", "branch", "base_branch", "work_dir", "kind"}
    updates = {key: value for key, value in patch.items() if key in allowed}
    if not updates:
        return get_workspace(conn, workspace_id)
    updates["updated_at"] = utc_now()
    columns = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(f"UPDATE workspaces SET {columns} WHERE id = ?", (*updates.values(), workspace_id))
    return get_workspace(conn, workspace_id)


def has_workspace(conn: sqlite3.Connection, workspace_id: str) -> bool:
    return conn.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone() is not None
