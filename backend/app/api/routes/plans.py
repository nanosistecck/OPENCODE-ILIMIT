from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ...domain import plans as rules
from ..deps import get_db
from ..schemas import PlanIn, PlanOut, PlanVersionOut
from ..serializers import plan_out

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{workspace_id}", response_model=PlanOut | None)
def get_plan(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return plan_out(conn, workspace_id)


@router.put("/{workspace_id}", response_model=PlanOut)
def save_plan(workspace_id: str, payload: PlanIn, conn: sqlite3.Connection = Depends(get_db)):
    rules.save_plan_version(conn, workspace_id, payload.model_dump())
    return plan_out(conn, workspace_id)


@router.get("/{workspace_id}/versions", response_model=list[PlanVersionOut])
def list_versions(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)):
    plan = plan_out(conn, workspace_id)
    return plan["versions"] if plan else []
