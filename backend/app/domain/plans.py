"""Planos versionados, validação de dependências e geração de fila em transação."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .errors import DomainError, NotFoundError
from .projects import get_workspace
from .utils import new_id, utc_now


def validate_steps(steps: list[dict[str, Any]]) -> None:
    """IDs únicos, dependências da mesma versão, sem ciclos e respeitando a ordem."""
    ids = [step["id"] for step in steps]
    if len(ids) != len(set(ids)):
        raise DomainError("IDs de etapa duplicados.", code="DUPLICATE_STEP_ID", status=422)
    orders = [step["order"] for step in steps]
    if len(orders) != len(set(orders)):
        raise DomainError("Ordem de etapa duplicada.", code="DUPLICATE_ORDER", status=422)
    by_id = {step["id"]: step for step in steps}

    for step in steps:
        for dependency in step.get("dependencies") or []:
            if dependency == step["id"]:
                raise DomainError("Etapa não pode depender de si mesma.", code="CYCLE", status=422)
            target = by_id.get(dependency)
            if target is None:
                raise DomainError("Dependência não pertence a esta versão.", code="FOREIGN_DEPENDENCY", status=422)
            if target["order"] >= step["order"]:
                raise DomainError("Dependência deve vir antes na ordem.", code="ORDER_VIOLATION", status=422)

    # Verificação explícita de ciclos (Kahn), mesmo com a regra de ordem acima.
    indegree = {step_id: len(step.get("dependencies") or []) for step_id, step in by_id.items()}
    queue = [step_id for step_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for step in steps:
            if current in (step.get("dependencies") or []):
                indegree[step["id"]] -= 1
                if indegree[step["id"]] == 0:
                    queue.append(step["id"])
    if visited != len(by_id):
        raise DomainError("Dependências formam um ciclo.", code="CYCLE", status=422)


def _get_plan_row(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM plans WHERE workspace_id = ?", (workspace_id,)).fetchone()
    return dict(row) if row else None


def get_plan(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    get_workspace(conn, workspace_id)
    plan = _get_plan_row(conn, workspace_id)
    if plan is None:
        return None
    versions: list[dict[str, Any]] = []
    for version in conn.execute(
        "SELECT * FROM plan_versions WHERE plan_id = ? ORDER BY version", (plan["id"],)
    ):
        item = dict(version)
        item["steps"] = [
            _step_out(step) for step in conn.execute(
                "SELECT * FROM plan_steps WHERE version_id = ? ORDER BY step_order", (item["id"],)
            )
        ]
        versions.append(item)
    current = next((v for v in versions if v["version"] == plan["current_version"]), None)
    return {
        **plan,
        "versions": versions,
        "steps": current["steps"] if current else [],
    }


def _step_out(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["dependencies"] = json.loads(item["dependencies"] or "[]")
    item["order"] = item.pop("step_order")
    item["acceptanceCriteria"] = item.pop("acceptance_criteria")
    return item


def save_plan_version(
    conn: sqlite3.Connection, workspace_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    get_workspace(conn, workspace_id)
    steps = payload.get("steps") or []
    if not steps:
        raise DomainError("Plano precisa de ao menos uma etapa.", code="VALIDATION", status=422)
    validate_steps(steps)
    now = utc_now()
    with conn:
        plan = _get_plan_row(conn, workspace_id)
        if plan is None:
            plan_id = new_id("plan")
            conn.execute(
                "INSERT INTO plans (id, workspace_id, objective, status, current_version, created_at, updated_at) "
                "VALUES (?, ?, ?, 'draft', 0, ?, ?)",
                (plan_id, workspace_id, payload.get("objective") or "", now, now),
            )
            plan = _get_plan_row(conn, workspace_id)
        version_number = int(plan["current_version"]) + 1
        version_id = new_id("pv")
        conn.execute(
            "INSERT INTO plan_versions (id, plan_id, version, objective, created_at) VALUES (?, ?, ?, ?, ?)",
            (version_id, plan["id"], version_number, payload.get("objective") or "", now),
        )
        for step in steps:
            conn.execute(
                "INSERT INTO plan_steps (id, version_id, step_order, title, description, dependencies, "
                "acceptance_criteria, prompt, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    step["id"],
                    version_id,
                    step["order"],
                    step.get("title") or "",
                    step.get("description") or "",
                    json.dumps(step.get("dependencies") or [], ensure_ascii=False),
                    step.get("acceptanceCriteria") or "",
                    step.get("prompt") or "",
                    step.get("status") or "pending",
                ),
            )
        conn.execute(
            "UPDATE plans SET objective = ?, current_version = ?, updated_at = ? WHERE id = ?",
            (payload.get("objective") or "", version_number, now, plan["id"]),
        )
    return get_plan(conn, workspace_id)


def set_plan_status(conn: sqlite3.Connection, workspace_id: str, status: str) -> dict[str, Any]:
    plan = _get_plan_row(conn, workspace_id)
    if plan is None:
        raise NotFoundError("Plano não encontrado.")
    with conn:
        conn.execute(
            "UPDATE plans SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), plan["id"]),
        )
    return get_plan(conn, workspace_id)


def get_version(conn: sqlite3.Connection, workspace_id: str, version_id: str) -> dict[str, Any]:
    plan = _get_plan_row(conn, workspace_id)
    if plan is None:
        raise NotFoundError("Plano não encontrado.")
    row = conn.execute(
        "SELECT * FROM plan_versions WHERE id = ? AND plan_id = ?", (version_id, plan["id"])
    ).fetchone()
    if row is None:
        raise NotFoundError("Versão não pertence a este espaço.")
    item = dict(row)
    item["steps"] = [
        _step_out(step) for step in conn.execute(
            "SELECT * FROM plan_steps WHERE version_id = ? ORDER BY step_order", (version_id,)
        )
    ]
    return item
