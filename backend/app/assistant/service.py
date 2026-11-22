"""Serviços de chat, análise, proposta de plano e revisão — todos por workspace_id."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..config import settings
from ..domain import batches as batch_rules
from ..domain import conversations as chat_rules
from ..domain import plans as plan_rules
from ..domain import projects as project_rules
from ..domain.errors import DomainError
from ..domain.utils import new_id, utc_now
from ..git import service as git_service
from ..opencode.client import OpenCodeClient
from ..queue import persistence as queue_store
from ..queue.engine import engine


def _client(conn: sqlite3.Connection) -> OpenCodeClient:
    return OpenCodeClient(queue_store.get_settings(conn)['executable'])


def _workspace_context(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    workspace = project_rules.get_workspace(conn, workspace_id)
    project = project_rules.get_project(conn, workspace['project_id'])
    verification = git_service.verify(conn, workspace_id)
    files: list[str] = []
    path = verification.get('path') or ''
    if path and Path(path).exists():
        try:
            files = [
                str(item.relative_to(path)).replace('\\', '/')
                for item in Path(path).rglob('*')
                if item.is_file() and '.git' not in item.parts
            ][:80]
        except OSError:
            files = []
    return {
        'workspace': workspace,
        'project': project,
        'verification': verification,
        'files': files,
    }


def message_out(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    return {
        'id': data['id'], 'conversationId': data['conversation_id'],
        'role': data['role'], 'content': data['content'] or '',
        'createdAt': data['created_at'], 'status': data['status'],
        'error': data.get('error') or '', 'partial': data.get('partial') or '',
        'chatAttemptId': data.get('chat_attempt_id') or '',
        'sessionId': data.get('session_id') or '', 'kind': data.get('kind') or 'chat',
    }


def chat_state(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    conversations = []
    for conversation in chat_rules.list_conversations(conn, workspace_id):
        item = dict(conversation)
        item['messages'] = [
            message_out(row) for row in conn.execute(
                'SELECT * FROM messages WHERE workspace_id = ? AND conversation_id = ? '
                'ORDER BY position, created_at', (workspace_id, item['id'])
            )
        ]
        conversations.append({
            'id': item['id'], 'workspaceId': workspace_id, 'title': item['title'],
            'messages': item['messages'], 'activity': [],
            'sessionId': item.get('session_id') or '',
            'sessionKind': item.get('session_kind') or 'chat',
            'sessionStatus': item.get('session_status') or 'none',
            'summary': item.get('summary') or '',
            'updatedAt': item.get('updated_at') or item['created_at'],
        })
    return {'workspaceId': workspace_id, 'conversations': conversations,
            'queueRunning': bool(engine._tasks)}


async def _wait_stable(workspace_id: str, timeout: float = 12.0) -> None:
    """Aguarda a fila terminar antes de analisar o estado atual da worktree."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(not task.done() for task in engine._tasks.values()):
            return
        await asyncio.sleep(0.15)
    raise DomainError(
        'A fila ainda está alterando a worktree. Aguarde a execução estabilizar.',
        code='WORKSPACE_BUSY',
    )


async def send_chat(
    conn: sqlite3.Connection, workspace_id: str, conversation_id: str, content: str
) -> dict[str, Any]:
    conversation = chat_rules.get_conversation(conn, workspace_id, conversation_id)
    text = (content or '').strip()
    if not text:
        raise DomainError('Mensagem vazia.', code='VALIDATION', status=422)
    attempt_id = new_id('chatatt')
    now = utc_now()
    with conn:
        position = conn.execute(
            'SELECT COALESCE(MAX(position), 0) + 1 FROM messages WHERE conversation_id = ?',
            (conversation_id,),
        ).fetchone()[0]
        conn.execute(
            'INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, '
            'status, created_at, chat_attempt_id, kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id('msg'), conversation_id, workspace_id, 'user', text, position,
             'sent', now, attempt_id, 'chat'),
        )
        reply_id = new_id('msg')
        conn.execute(
            'INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, '
            'status, created_at, chat_attempt_id, kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (reply_id, conversation_id, workspace_id, 'assistant', '', position + 1,
             'responding', now, attempt_id, 'chat'),
        )

    context = _workspace_context(conn, workspace_id)
    session_id = conversation.get('session_id') or ''
    cwd = context['verification'].get('path') or str(settings.data_dir)
    prefix = (
        f"Objetivo do espaço: {context['project'].get('objective') or 'não informado'}\n"
        f"Branch: {context['workspace']['branch']}\n"
        f"Pasta: {cwd}\n\n"
    )

    async def on_line(line: str) -> None:
        with conn:
            conn.execute(
                'UPDATE messages SET partial = ? WHERE id = ?',
                ((line[:20_000]), reply_id),
            )

    try:
        result = await _client(conn).run(
            prefix + text, cwd, session_id=session_id,
            on_line=on_line, timeout=settings.opencode_timeout,
        )
    except Exception as exc:
        with conn:
            conn.execute(
                "UPDATE messages SET status = 'failed', error = ?, partial = ? WHERE id = ?",
                (str(exc)[:4000], '', reply_id),
            )
        return chat_state(conn, workspace_id)

    status = 'completed' if result.status == 'success' else 'failed'
    final_text = result.final_text or result.output[-8000:] or '(sem conteúdo)'
    with conn:
        conn.execute(
            'UPDATE messages SET content = ?, status = ?, error = ?, session_id = ? WHERE id = ?',
            (final_text[:20_000], status, result.error[:4000], result.session_id or session_id, reply_id),
        )
        conn.execute(
            'UPDATE conversations SET session_id = ?, session_status = ?, updated_at = ? WHERE id = ?',
            (result.session_id or session_id, 'active' if result.session_id or session_id else 'none',
             utc_now(), conversation_id),
        )
    return chat_state(conn, workspace_id)


async def new_session(conn: sqlite3.Connection, workspace_id: str, conversation_id: str) -> dict[str, Any]:
    conversation = chat_rules.get_conversation(conn, workspace_id, conversation_id)
    messages = chat_rules.list_messages(conn, workspace_id, conversation_id)
    summary = '\n'.join(
        f"{item['role']}: {(item['content'] or '')[:400]}" for item in messages[-8:]
    )[:8000]
    new_conversation = chat_rules.create_conversation(
        conn, workspace_id, title=f"Retomada · {conversation['title']}"
    )
    with conn:
        conn.execute(
            'UPDATE conversations SET summary = ?, session_status = ? WHERE id = ?',
            (summary, 'restarted', new_conversation['id']),
        )
        conn.execute(
            'INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, status, created_at, kind) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id('msg'), new_conversation['id'], workspace_id, 'assistant',
             'Nova sessão iniciada com resumo do contexto anterior.', 0, 'sent', utc_now(), 'system'),
        )
    return chat_state(conn, workspace_id)


async def analyze_project(conn: sqlite3.Connection, workspace_id: str, objective: str) -> dict[str, Any]:
    await _wait_stable(workspace_id)
    context = _workspace_context(conn, workspace_id)
    conversation = chat_rules.ensure_conversation(conn, workspace_id)
    analysis_id = new_id('analysis')
    cwd = context['verification'].get('path') or str(settings.data_dir)
    prompt = (
        "Analise este espaço de trabalho SEM alterar arquivos nem executar comandos de escrita.\n"
        f"Objetivo informado: {objective or context['project'].get('objective') or 'não informado'}\n"
        f"Projeto: {context['project']['name']} — {context['project'].get('objective') or ''}\n"
        f"Regras: {context['project'].get('rules') or 'nenhuma'}\n"
        f"Branch: {context['workspace']['branch']} (base {context['workspace']['base_branch']})\n"
        f"Arquivos disponíveis: {', '.join(context['files']) or 'nenhum'}\n\n"
        "Responda em JSON com: features (lista), gaps (lista), evidence (lista de arquivos/comandos), "
        "assumptions (lista), questions (lista). Identifique o que já existe e uma lacuna real. "
        "Mencione comandos de validação existentes sem afirmar que foram executados.\n"
    )
    result = await _client(conn).run(prompt, cwd, session_id=conversation.get('session_id') or '')
    data = _extract_json(result.final_text or result.output)
    content = result.final_text or result.output[-8000:]
    valid = result.status == 'success' and isinstance(data, dict)
    with conn:
        conn.execute(
            'INSERT INTO analyses (id, workspace_id, conversation_id, content, evidence, assumptions, '
            'questions, git_state, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (analysis_id, workspace_id, conversation['id'], content[:30_000],
             json.dumps(_as_list(data.get('evidence') if data else []), ensure_ascii=False),
             json.dumps(_as_list(data.get('assumptions') if data else []), ensure_ascii=False),
             json.dumps(_as_list(data.get('questions') if data else []), ensure_ascii=False),
             json.dumps(context['verification'], ensure_ascii=False), utc_now()),
        )
        conn.execute(
            'INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, status, created_at, kind) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id('msg'), conversation['id'], workspace_id, 'assistant', content[:30_000],
             _next_position(conn, conversation['id']),
             'completed' if valid else 'failed', utc_now(), 'analysis'),
        )
    return {
        'id': analysis_id, 'workspaceId': workspace_id, 'content': content,
        'evidence': _as_list(data.get('evidence') if data else []),
        'assumptions': _as_list(data.get('assumptions') if data else []),
        'questions': _as_list(data.get('questions') if data else []),
        'gitState': context['verification'], 'valid': valid,
        'error': '' if valid else (result.error or 'Resposta sem JSON estruturado.'),
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _next_position(conn: sqlite3.Connection, conversation_id: str) -> int:
    return int(conn.execute(
        'SELECT COALESCE(MAX(position), 0) + 1 FROM messages WHERE conversation_id = ?',
        (conversation_id,),
    ).fetchone()[0])


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    candidates = [text]
    if '```' in text:
        candidates.extend(text.split('```')[1::2])
    for candidate in candidates:
        start, end = candidate.find('{'), candidate.rfind('}')
        if start < 0 or end <= start:
            continue
        try:
            value = json.loads(candidate[start:end + 1])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


async def generate_proposal(
    conn: sqlite3.Connection, workspace_id: str, analysis_id: str, answers: str = ''
) -> dict[str, Any]:
    await _wait_stable(workspace_id)
    row = conn.execute('SELECT * FROM analyses WHERE id = ? AND workspace_id = ?',
                       (analysis_id, workspace_id)).fetchone()
    if row is None:
        raise DomainError('Análise não encontrada.', code='NOT_FOUND')
    analysis = dict(row)
    context = _workspace_context(conn, workspace_id)
    conversation = chat_rules.ensure_conversation(conn, workspace_id)
    prompt = (
        "Produza um plano estruturado em JSON para este espaço. Não altere arquivos.\n"
        f"Análise anterior:\n{analysis['content'][:12000]}\n\n"
        f"Respostas do usuário: {answers or 'nenhuma ainda'}\n"
        f"Branch: {context['workspace']['branch']}\n\n"
        "JSON obrigatório: {\"objective\",\"scope\",\"decisions\":[{\"text\",\"needsAnswer\"}],"
        "\"questions\":[\"...\"],\"steps\":[{\"title\",\"objective\",\"dependencies\":[índices 1-based],"
        "\"prompt\",\"acceptanceCriteria\"}]}. Dependências devem vir antes e não formar ciclos.\n"
    )
    result = await _client(conn).run(
        prompt, context['verification'].get('path') or str(settings.data_dir),
        session_id=conversation.get('session_id') or '',
    )
    data = _extract_json(result.final_text or result.output)
    proposal_id = new_id('proposal')
    validation_error = ''
    steps: list[dict[str, Any]] = []
    if result.status != 'success':
        validation_error = result.error or 'Resposta interrompida.'
    elif not isinstance(data, dict):
        validation_error = 'O OpenCode não devolveu um JSON estruturado.'
    else:
        steps, validation_error = _normalize_steps(data.get('steps'))
        if not str(data.get('objective') or '').strip():
            validation_error = validation_error or 'Objetivo ausente na proposta.'

    status = 'invalid' if validation_error else 'draft'
    with conn:
        conn.execute(
            'INSERT INTO plan_proposals (id, workspace_id, conversation_id, message_id, analysis_id, status, '
            'objective, scope, decisions, questions, steps, validation_error, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (proposal_id, workspace_id, conversation['id'], None, analysis_id, status,
             str(data.get('objective') or '')[:4000] if data else '',
             str(data.get('scope') or '')[:4000] if data else '',
             json.dumps(data.get('decisions') or [], ensure_ascii=False) if data else '[]',
             json.dumps(_as_list(data.get('questions') if data else []), ensure_ascii=False),
             json.dumps(steps, ensure_ascii=False), validation_error, utc_now()),
        )
        conn.execute(
            'INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, status, created_at, kind) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id('msg'), conversation['id'], workspace_id, 'assistant',
             (result.final_text or result.output)[:30_000], _next_position(conn, conversation['id']),
             'completed' if not validation_error else 'failed', utc_now(), 'proposal'),
        )
    return proposal_out(conn, workspace_id, proposal_id)


def _normalize_steps(raw: Any) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(raw, list) or not raw:
        return [], 'Nenhuma etapa válida na proposta.'
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return [], f'Etapa {index} não é um objeto.'
        title = str(item.get('title') or '').strip()
        prompt = str(item.get('prompt') or '').strip()
        acceptance = str(item.get('acceptanceCriteria') or '').strip()
        if not title or not prompt or not acceptance:
            return [], f'Etapa {index} incompleta (título, prompt ou aceite ausente).'
        deps_raw = item.get('dependencies') or []
        if not isinstance(deps_raw, list):
            return [], f'Dependências da etapa {index} são inválidas.'
        deps: list[int] = []
        for dep in deps_raw:
            value = str(dep).strip()
            if value.startswith('step-'):
                try:
                    deps.append(int(value.split('-', 1)[1]))
                    continue
                except (TypeError, ValueError):
                    return [], f'Dependência inválida na etapa {index}.'
            try:
                deps.append(int(value))
            except (TypeError, ValueError):
                return [], f'Dependência inválida na etapa {index}.'
        steps.append({
            'id': f'step-{index}',
            'order': index,
            'title': title[:500],
            'objective': str(item.get('objective') or '')[:2000],
            'dependencies': deps,
            'prompt': prompt[:20_000],
            'acceptanceCriteria': acceptance[:4000],
        })
    for step in steps:
        for dep in step['dependencies']:
            if dep < 1 or dep > len(steps):
                return [], f'Dependência {dep} não existe na proposta.'
            if dep >= step['order']:
                return [], 'Dependência deve vir antes na ordem.'
    normalized = [
        {**step, 'dependencies': [f'step-{dep}' for dep in step['dependencies']]}
        for step in steps
    ]
    try:
        plan_rules.validate_steps([
            {'id': item['id'], 'order': item['order'], 'dependencies': item['dependencies']}
            for item in normalized
        ])
    except DomainError as exc:
        return [], exc.message
    return normalized, ''


def proposal_out(conn: sqlite3.Connection, workspace_id: str, proposal_id: str) -> dict[str, Any]:
    row = conn.execute(
        'SELECT * FROM plan_proposals WHERE id = ? AND workspace_id = ?', (proposal_id, workspace_id)
    ).fetchone()
    if row is None:
        raise DomainError('Proposta não encontrada.', code='NOT_FOUND')
    data = dict(row)
    for key in ('decisions', 'questions', 'steps'):
        try:
            data[key] = json.loads(data[key] or '[]')
        except json.JSONDecodeError:
            data[key] = []
    return {
        'id': data['id'], 'workspaceId': workspace_id, 'analysisId': data['analysis_id'],
        'status': data['status'], 'objective': data['objective'], 'scope': data['scope'],
        'decisions': data['decisions'], 'questions': data['questions'],
        'steps': data['steps'], 'validationError': data['validation_error'],
        'createdAt': data['created_at'],
    }


def latest_proposal(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        'SELECT id FROM plan_proposals WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 1',
        (workspace_id,),
    ).fetchone()
    return proposal_out(conn, workspace_id, row['id']) if row else None


def approve_proposal(
    conn: sqlite3.Connection,
    workspace_id: str,
    proposal_id: str,
    edits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal = proposal_out(conn, workspace_id, proposal_id)
    if proposal['status'] == 'invalid' and not edits:
        raise DomainError('Proposta inválida não pode ser aprovada sem revisão.', code='INVALID_PLAN')
    steps = edits.get('steps') if edits else proposal['steps']
    objective = (edits or {}).get('objective', proposal['objective'])
    normalized, error = _normalize_steps(steps)
    if error:
        raise DomainError(error, code='INVALID_PLAN', status=422)
    plan = plan_rules.save_plan_version(conn, workspace_id, {
        'objective': objective,
        'steps': [
            {
                'id': item['id'], 'order': item['order'], 'title': item['title'],
                'description': item.get('objective') or '',
                'dependencies': item['dependencies'],
                'acceptanceCriteria': item['acceptanceCriteria'],
                'prompt': item['prompt'],
            }
            for item in normalized
        ],
    })
    verification = git_service.verify(conn, workspace_id)
    with conn:
        conn.execute(
            "UPDATE plans SET source_analysis_id = ?, source_proposal_id = ?, branch = ?, "
            "approved_at = ?, status = 'approved' WHERE workspace_id = ?",
            (proposal['analysisId'], proposal_id, verification['branch'], utc_now(), workspace_id),
        )
        conn.execute("UPDATE plan_proposals SET status = 'approved' WHERE id = ?", (proposal_id,))
    from ..api.serializers import plan_out

    return plan_out(conn, workspace_id)


def create_batch_for_version(
    conn: sqlite3.Connection, workspace_id: str, version_id: str, force: bool = False
) -> dict[str, Any]:
    version = plan_rules.get_version(conn, workspace_id, version_id)
    if not force:
        existing = conn.execute(
            'SELECT id FROM batches WHERE workspace_id = ? AND source_version_id = ? ORDER BY created_at DESC LIMIT 1',
            (workspace_id, version_id),
        ).fetchone()
        if existing:
            from ..api.serializers import batch_out

            return batch_out(conn, workspace_id, {'id': existing['id']})
    batch = batch_rules.create_batch_from_version(conn, workspace_id, version)
    from ..api.serializers import batch_out

    return batch_out(conn, workspace_id, batch)


async def build_review(
    conn: sqlite3.Connection, workspace_id: str, batch_id: str
) -> dict[str, Any]:
    await _wait_stable(workspace_id)
    state = queue_store.batch_state(conn, workspace_id, batch_id)
    plan = plan_rules.get_plan(conn, workspace_id)
    version = next(
        (item for item in (plan or {}).get('versions', [])
         if item['id'] == (conn.execute(
             'SELECT source_version_id FROM batches WHERE id = ?', (batch_id,)
         ).fetchone() or {'source_version_id': ''})['source_version_id']),
        None,
    )
    verification = git_service.verify(conn, workspace_id)
    criteria: list[dict[str, Any]] = []
    for item in state['items']:
        attempt = next((a for a in state['attempts'] if a['itemId'] == item['id'] and a['status'] == 'success'), None)
        if item['status'] == 'done' and attempt:
            evidence = (attempt.get('result') or '')[:500]
            criterion_status = 'verified' if len(evidence) >= 20 else 'insufficient_evidence'
        elif item['status'] == 'pending':
            criterion_status = 'pending'
            evidence = 'Nenhuma tentativa concluída para este critério.'
        else:
            criterion_status = 'insufficient_evidence'
            evidence = (attempt or {}).get('error') or 'Sem evidência suficiente.'
        criteria.append({
            'itemId': item['id'], 'title': item['title'], 'status': criterion_status,
            'evidence': evidence, 'acceptanceCriteria': item.get('acceptanceCriteria') or '',
            'attemptId': (attempt or {}).get('id') or '',
        })
    missing = [item for item in criteria if item['status'] != 'verified']
    report = {
        'workspaceId': workspace_id, 'batchId': batch_id,
        'planVersionId': (version or {}).get('id') or '',
        'branch': verification['branch'], 'head': verification['head'],
        'headAtExecution': (state['attempts'][0].get('headBefore') if state['attempts'] else '') or '',
        'gitChangedSinceExecution': bool(
            verification['head'] and state['attempts']
            and verification['head'] != state['attempts'][0].get('headBefore')
        ),
        'criteria': criteria,
        'suggestedSteps': [
            {
                'id': f'suggested-{index}', 'order': index, 'title': f"Completar: {item['title']}",
                'description': item['acceptanceCriteria'], 'dependencies': [],
                'acceptanceCriteria': item['acceptanceCriteria'],
                'prompt': f"Revise o critério pendente: {item['acceptanceCriteria']}",
                'reason': item['status'],
            }
            for index, item in enumerate(missing, 1)
        ],
    }
    review_id = new_id('review')
    with conn:
        conn.execute(
            'INSERT INTO reviews (id, workspace_id, batch_id, version_id, report, head_before, head_after, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (review_id, workspace_id, batch_id, report.get('planVersionId'),
             json.dumps(report, ensure_ascii=False), report['headAtExecution'],
             report['head'], utc_now()),
        )
    return report


def latest_review(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        'SELECT report FROM reviews WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 1',
        (workspace_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row['report'])
    except json.JSONDecodeError:
        return None
