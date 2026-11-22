from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...domain import projects as rules
from ..schemas import ProjectIn, ProjectOut, ProjectPatch, WorkspaceIn, WorkspaceOut
from ..serializers import project_out, workspace_out
from ..deps import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, conn: sqlite3.Connection = Depends(get_db)):
    return project_out(conn, rules.create_project(conn, payload.model_dump()))


@router.get("", response_model=list[ProjectOut])
def list_projects(conn: sqlite3.Connection = Depends(get_db)):
    return [project_out(conn, row) for row in rules.list_projects(conn)]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return project_out(conn, rules.get_project(conn, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectPatch, conn: sqlite3.Connection = Depends(get_db)):
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "baseBranch" in patch:
        patch["base_branch"] = patch.pop("baseBranch")
    if "repoPath" in patch:
        patch["repo_path"] = patch.pop("repoPath")
    return project_out(conn, rules.update_project(conn, project_id, patch))


@router.get("/{project_id}/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(project_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return [workspace_out(row) for row in rules.list_workspaces(conn, project_id)]


@router.post(
    "/{project_id}/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED
)
def create_workspace(
    project_id: str, payload: WorkspaceIn, conn: sqlite3.Connection = Depends(get_db)
):
    return workspace_out(rules.create_workspace(conn, project_id, payload.model_dump()))
