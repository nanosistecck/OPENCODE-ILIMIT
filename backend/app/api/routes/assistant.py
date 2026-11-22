"""Rotas do fluxo chat → análise → plano → lote → revisão."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ...assistant import service
from ..deps import get_db
from ..schemas import AnalysisIn, ApproveIn, AssistantBatchIn, ChatMessageIn, ProposalIn

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/chat/{workspace_id}/state")
def chat_state(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return service.chat_state(conn, workspace_id)


@router.post("/chat/{workspace_id}/messages")
async def send_message(
    workspace_id: str, payload: ChatMessageIn,
    conversationId: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    from ...domain.conversations import ensure_conversation

    conversation_id = conversationId or ensure_conversation(conn, workspace_id)['id']
    return await service.send_chat(conn, workspace_id, conversation_id, payload.content)


@router.post("/chat/{workspace_id}/new-session")
async def new_session(
    workspace_id: str, conversationId: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    from ...domain.conversations import ensure_conversation

    conversation_id = conversationId or ensure_conversation(conn, workspace_id)['id']
    return await service.new_session(conn, workspace_id, conversation_id)


@router.post("/analyze/{workspace_id}")
async def analyze(
    workspace_id: str, payload: AnalysisIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return await service.analyze_project(conn, workspace_id, payload.objective)


@router.post("/plan/{workspace_id}/proposal")
async def generate_proposal(
    workspace_id: str, payload: ProposalIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return await service.generate_proposal(conn, workspace_id, payload.analysisId, payload.answers)


@router.get("/plan/{workspace_id}/proposal")
def get_proposal(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict | None:
    return service.latest_proposal(conn, workspace_id)


@router.post("/plan/{workspace_id}/approve")
def approve(
    workspace_id: str, payload: ApproveIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    edits = None
    if payload.objective is not None or payload.steps is not None:
        edits = {'objective': payload.objective, 'steps': payload.steps}
    return service.approve_proposal(conn, workspace_id, payload.proposalId, edits)


@router.post("/plan/{workspace_id}/batch")
def create_batch(
    workspace_id: str, payload: AssistantBatchIn, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return service.create_batch_for_version(conn, workspace_id, payload.versionId, payload.force)


@router.post("/review/{workspace_id}")
async def review(
    workspace_id: str, batchId: str, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return await service.build_review(conn, workspace_id, batchId)


@router.get("/review/{workspace_id}")
def get_review(workspace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict | None:
    return service.latest_review(conn, workspace_id)
