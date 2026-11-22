from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ...domain import batches as batch_rules
from ...domain import conversations as conversation_rules
from ...domain import plans as plan_rules
from ...domain import projects as project_rules
from ...domain.errors import NotFoundError
from ...domain.utils import new_id, utc_now
from ..deps import get_db
from ..schemas import (
    ConversationOut,
    GitOut,
    MessageIn,
    MessageOut,
    WorkspaceOut,
    WorkspacePatch,
    WorkspaceStateOut,
)
from ..serializers import (
    batch_out,
    conversation_out,
    git_out,
    workspace_out,
    workspace_state_out,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return workspace_out(project_rules.get_workspace(conn, workspace_id))


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str, payload: WorkspacePatch, conn: sqlite3.Connection = Depends(get_db)
):
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "baseBranch" in patch:
        patch["base_branch"] = patch.pop("baseBranch")
    if "workDir" in patch:
        patch["work_dir"] = patch.pop("workDir")
    return workspace_out(project_rules.update_workspace(conn, workspace_id, patch))


@router.get("/{workspace_id}/state", response_model=WorkspaceStateOut)
def get_workspace_state(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return workspace_state_out(conn, workspace_id)


@router.get("/{workspace_id}/conversations", response_model=list[ConversationOut])
def list_conversations(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return [
        conversation_out(conn, workspace_id, row)
        for row in conversation_rules.list_conversations(conn, workspace_id)
    ]


@router.post(
    "/{workspace_id}/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED
)
def create_conversation(
    workspace_id: str,
    title: str = Query(default="Conversa"),
    conn: sqlite3.Connection = Depends(get_db),
):
    row = conversation_rules.create_conversation(conn, workspace_id, title)
    return conversation_out(conn, workspace_id, row)


@router.post("/{workspace_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    workspace_id: str,
    payload: MessageIn,
    conversationId: str = Query(..., alias="conversationId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    message = conversation_rules.add_message(
        conn, workspace_id, conversationId, "user", payload.content, "sent"
    )
    from ..serializers import message_out

    return message_out(message)


@router.get("/{workspace_id}/batches", response_model=list)
def list_batches(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return [
        batch_out(conn, workspace_id, row)
        for row in batch_rules.list_batches_with_items(conn, workspace_id)
    ]


@router.get("/{workspace_id}/attempts", response_model=list)
def list_attempts(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    from ...queue.persistence import list_attempts as store_list

    project_rules.get_workspace(conn, workspace_id)
    return store_list(conn, workspace_id)


@router.get("/{workspace_id}/git", response_model=GitOut)
def get_git(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return git_out(conn, project_rules.get_workspace(conn, workspace_id))


@router.post("/{workspace_id}/plan/review", response_model=dict)
def review_plan(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    plan = plan_rules.set_plan_status(conn, workspace_id, "in_review")
    return {"id": plan["id"], "status": plan["status"], "version": plan["current_version"]}


@router.post("/{workspace_id}/queue", response_model=dict, status_code=status.HTTP_201_CREATED)
def generate_queue(
    workspace_id: str,
    versionId: str | None = Query(default=None, alias="versionId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    plan = plan_rules.get_plan(conn, workspace_id)
    if plan is None:
        raise NotFoundError("Plano não encontrado.")
    version_id = versionId or next(
        (version["id"] for version in plan["versions"] if version["version"] == plan["current_version"]),
        None,
    )
    if version_id is None:
        raise NotFoundError("Versão do plano não encontrada.")
    version = plan_rules.get_version(conn, workspace_id, version_id)
    batch = batch_rules.create_batch_from_version(conn, workspace_id, version)
    return batch_out(conn, workspace_id, batch)
