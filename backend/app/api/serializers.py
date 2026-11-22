"""Converte linhas do banco para os formatos esperados pelo frontend."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..domain import batches as batch_rules
from ..domain import conversations as conversation_rules
from ..domain import plans as plan_rules
from ..domain import projects as project_rules


def project_out(conn: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
    workspaces = conn.execute(
        "SELECT id FROM workspaces WHERE project_id = ? ORDER BY created_at", (row["id"],)
    ).fetchall()
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["objective"] or "",
        "objective": row["objective"] or "",
        "rules": row["rules"] or "",
        "baseBranch": row["base_branch"],
        "repoPath": row["repo_path"],
        "workspaceIds": [item["id"] for item in workspaces],
    }


def workspace_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "name": row["name"],
        "branch": row["branch"],
        "base": row["base_branch"],
        "baseBranch": row["base_branch"],
        "workDir": row["work_dir"] or "",
        "kind": row["kind"],
        "createdAt": row["created_at"],
    }


def message_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "conversationId": row["conversation_id"],
        "role": row["role"],
        "content": row["content"],
        "createdAt": row["created_at"],
        "status": row["status"],
    }


def conversation_out(conn: sqlite3.Connection, workspace_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspaceId": workspace_id,
        "title": row["title"],
        "messages": [
            message_out(message)
            for message in conversation_rules.list_messages(conn, workspace_id, row["id"])
        ],
        "activity": [],
    }


def plan_out(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    plan = plan_rules.get_plan(conn, workspace_id)
    if plan is None:
        return None
    return {
        "id": plan["id"],
        "workspaceId": workspace_id,
        "objective": plan["objective"] or "",
        "version": plan["current_version"],
        "status": plan["status"],
        "steps": plan["steps"],
        "versions": [
            {
                "id": version["id"],
                "version": version["version"],
                "objective": version["objective"],
                "createdAt": version["created_at"],
                "steps": version["steps"],
            }
            for version in plan["versions"]
        ],
    }


def batch_out(conn: sqlite3.Connection, workspace_id: str, batch: dict[str, Any]) -> dict[str, Any]:
    full = batch_rules.batch_with_items(conn, workspace_id, batch["id"])
    return {
        "id": full["id"],
        "workspaceId": workspace_id,
        "name": full["name"],
        "status": full["status"],
        "pauseRequested": False,
        "cursor": full["cursor"],
        "items": full["items"],
        "sourceVersionId": full["source_version_id"],
        "createdAt": full["created_at"],
    }


def git_out(conn: sqlite3.Connection, workspace: dict[str, Any]) -> dict[str, Any]:
    """Dados reais quando o espaço está vinculado; marcador de pendência quando não está."""
    from ..git import local, service

    base: dict[str, Any] = {
        "workspaceId": workspace["id"],
        "branch": workspace["branch"],
        "base": workspace["base_branch"],
        "workDir": workspace.get("git_work_dir") or workspace["work_dir"] or "",
        "head": "",
        "repoRoot": workspace.get("git_repo_root") or "",
        "gitStatus": workspace.get("git_status", "pending"),
        "linked": False,
        "registeredOnly": True,
        "simulated": True,
        "summary": {},
        "files": [],
        "operations": [],
        "verification": {},
        "diff": [],
        "commits": [],
        "pullRequest": {
            "id": "pr-pending",
            "title": "Pull request — integração futura",
            "source": workspace["branch"],
            "target": workspace["base_branch"],
            "status": "draft",
            "verifications": [
                {
                    "id": "verify-pending",
                    "name": "Verificação Git",
                    "status": "pending",
                    "conclusion": "Integração futura",
                }
            ],
        },
    }

    if workspace.get("git_status") == "ready" and workspace.get("git_work_dir"):
        current = local.state(workspace["git_work_dir"])
        status = service.status_payload(conn, workspace["id"])
        base.update({
            "branch": current.get("branch") or workspace["branch"],
            "head": current.get("head", ""),
            "linked": True,
            "registeredOnly": False,
            "simulated": False,
            "summary": status.get("summary", {}),
            "files": status.get("files", []),
            "operations": status.get("operations", []),
            "verification": service.verify(conn, workspace["id"]),
        })
    return base


def workspace_state_out(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    workspace = project_rules.get_workspace(conn, workspace_id)
    project = project_rules.get_project(conn, workspace["project_id"])
    conversation = conversation_rules.ensure_conversation(conn, workspace_id)
    batches = batch_rules.list_batches(conn, workspace_id)
    return {
        "workspace": workspace_out(workspace),
        "project": project_out(conn, project),
        "conversation": conversation_out(conn, workspace_id, conversation),
        "plan": plan_out(conn, workspace_id),
        "batch": batch_out(conn, workspace_id, batches[0]) if batches else None,
        "git": git_out(conn, workspace),
        "connection": "connected",
    }
