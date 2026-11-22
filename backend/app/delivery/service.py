"""Orquestração de commit, publicação e PR com vínculos persistidos."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from ..domain.errors import DomainError, NotFoundError
from ..domain.utils import new_id, utc_now
from ..git import local as git_local
from ..git import service as git_service
from ..queue.engine import engine
from . import gitops
from . import github as github_module

_PREVIEWS: dict[str, dict[str, Any]] = {}


def _workspace(conn: sqlite3.Connection, workspace_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace = conn.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,)).fetchone()
    if workspace is None:
        raise NotFoundError('Espaço não encontrado.')
    workspace = dict(workspace)
    verification = git_service.verify(conn, workspace_id)
    if not verification['ready']:
        raise DomainError(
            'Vínculo Git não confirmado: ' + ', '.join(verification['reasons']),
            code='LINK_NOT_READY',
        )
    info = git_local.probe(verification['path'])
    if info['ok']:
        verification['commonDir'] = info['commonDir']
    return workspace, verification


def _ensure_writable() -> None:
    if any(not task.done() for task in engine._tasks.values()):
        raise DomainError(
            'A fila está executando e pode alterar a worktree. '
            'Consultas estão disponíveis; aguarde o término para operações de escrita.',
            code='QUEUE_BUSY',
        )


def _repo_slug(url: str) -> str:
    value = (url or '').strip().removesuffix('.git')
    if '://' in value:
        value = value.split('://', 1)[1]
    if '@' in value:
        value = value.split('@', 1)[1]
    if '/' in value:
        value = value.split('/', 1)[1]
    return value.replace('\\', '/')


def state(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    workspace, verification = _workspace(conn, workspace_id)
    path = verification['path']
    remotes = gitops.remotes(path)
    ahead = {
        item['name']: gitops.ahead_count(path, item['name'], verification['branch'])
        for item in {remote['name']: remote for remote in remotes}.values()
    }
    gh = github_module.get_client().detect()
    commits = [dict(row) for row in conn.execute(
        'SELECT * FROM delivery_commits WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 30',
        (workspace_id,),
    )]
    pushes = [dict(row) for row in conn.execute(
        'SELECT * FROM delivery_pushes WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 30',
        (workspace_id,),
    )]
    prs = [dict(row) for row in conn.execute(
        'SELECT * FROM delivery_pull_requests WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 10',
        (workspace_id,),
    )]
    for item in commits + pushes + prs:
        if 'error' in item:
            item['error'] = gitops.sanitize(item['error'])
    return {
        'workspaceId': workspace_id, 'branch': verification['branch'],
        'head': verification['head'], 'path': path,
        'remotes': remotes, 'ahead': ahead, 'github': gh,
        'writable': not any(not task.done() for task in engine._tasks.values()),
        'commits': commits, 'pushes': pushes, 'pullRequests': prs,
    }


def preview(
    conn: sqlite3.Connection, workspace_id: str, selected_paths: list[str], message: str
) -> dict[str, Any]:
    _ensure_writable()
    _, verification = _workspace(conn, workspace_id)
    path = verification['path']
    status = git_local.status(path, verification.get('commonDir', ''))
    files = status.get('files', [])
    selected = set(selected_paths or [])
    staged = {item['path'] for item in files if item['staged']}
    outside = sorted(staged - selected)
    digest = gitops.index_digest(path)
    preview_id = new_id('preview')
    _PREVIEWS[preview_id] = {
        'workspaceId': workspace_id, 'digest': digest, 'head': verification['head'],
        'selected': sorted(selected), 'path': path, 'createdAt': utc_now(),
    }
    return {
        'previewId': preview_id, 'workspaceId': workspace_id,
        'branch': verification['branch'], 'head': verification['head'],
        'files': files, 'summary': status.get('summary', {}),
        'selected': sorted(selected), 'stagedOutsideSelection': outside,
        'message': message, 'digest': digest,
        'conflict': bool(outside) or status.get('summary', {}).get('conflicts', 0) > 0,
    }


def commit(
    conn: sqlite3.Connection,
    workspace_id: str,
    preview_id: str,
    selected_paths: list[str],
    message: str,
    batch_id: str = '',
    attempt_id: str = '',
) -> dict[str, Any]:
    _ensure_writable()
    preview_data = _PREVIEWS.get(preview_id)
    if not preview_data or preview_data['workspaceId'] != workspace_id:
        raise DomainError('Prévia não encontrada. Refaça a revisão.', code='PREVIEW_MISSING')
    _, verification = _workspace(conn, workspace_id)
    path = verification['path']
    current_digest = gitops.index_digest(path)
    if current_digest != preview_data['digest'] or verification['head'] != preview_data['head']:
        fresh = preview(conn, workspace_id, selected_paths, message)
        raise DomainError(
            'O HEAD ou o índice mudou desde a prévia. Revise novamente antes de confirmar.',
            code='STALE_PREVIEW', detail={'freshPreviewId': fresh['previewId']},
        )
    staged = set(gitops.staged_files(path))
    outside = sorted(staged - set(selected_paths))
    if outside:
        raise DomainError(
            'Existem alterações preparadas fora da seleção: ' + ', '.join(outside),
            code='STAGED_OUTSIDE_SELECTION', detail={'files': outside},
        )
    ok, error = gitops.stage(path, selected_paths)
    if not ok:
        _record_failure(conn, workspace_id, message, selected_paths, verification['head'],
                        error, batch_id, attempt_id)
        raise DomainError(error, code='STAGE_FAILED')
    staged_after = gitops.staged_files(path)
    if not staged_after:
        _record_failure(conn, workspace_id, message, selected_paths, verification['head'],
                        'Nenhuma alteração preparada para commit.', batch_id, attempt_id)
        raise DomainError('Nenhuma alteração preparada para commit.', code='NO_CHANGES')
    ok, error = gitops.commit(path, message)
    if not ok:
        current = gitops.staged_files(path)
        _record_failure(conn, workspace_id, message, selected_paths, verification['head'],
                        error, batch_id, attempt_id)
        raise DomainError(
            error + ' O índice foi preservado; corrija a causa e tente novamente.',
            code='COMMIT_FAILED', detail={'staged': current},
        )
    new_head = git_local.state(path)['head']
    if not new_head or new_head == verification['head']:
        raise DomainError('Commit não confirmado no Git.', code='COMMIT_UNCONFIRMED')
    commit_id = new_id('commit')
    with conn:
        conn.execute(
            'INSERT INTO delivery_commits (id, workspace_id, batch_id, attempt_id, hash, message, files, '
            'head_before, head_after, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (commit_id, workspace_id, batch_id or None, attempt_id or None, new_head, message,
             json.dumps(staged_after, ensure_ascii=False), verification['head'], new_head,
             'created', utc_now()),
        )
    _PREVIEWS.pop(preview_id, None)
    return {
        'id': commit_id, 'workspaceId': workspace_id, 'hash': new_head,
        'message': message, 'files': staged_after, 'headBefore': verification['head'],
        'status': 'created',
    }


def _record_failure(
    conn: sqlite3.Connection, workspace_id: str, message: str, files: list[str],
    head: str, error: str, batch_id: str, attempt_id: str,
) -> None:
    with conn:
        conn.execute(
            'INSERT INTO delivery_commits (id, workspace_id, batch_id, attempt_id, hash, message, files, '
            'head_before, status, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (new_id('commit'), workspace_id, batch_id or None, attempt_id or None, '', message,
             json.dumps(files, ensure_ascii=False), head, 'failed',
             gitops.sanitize(error), utc_now()),
        )


def push(
    conn: sqlite3.Connection, workspace_id: str, remote: str = '', commit_id: str = ''
) -> dict[str, Any]:
    _ensure_writable()
    _, verification = _workspace(conn, workspace_id)
    remotes = gitops.remotes(verification['path'])
    if not remote:
        remote = remotes[0]['name'] if remotes else 'origin'
    if remote not in {item['name'] for item in remotes}:
        raise DomainError('Remoto não encontrado neste repositório.', code='REMOTE_NOT_FOUND')
    result = gitops.push(verification['path'], remote, verification['branch'])
    status = 'pushed' if result['ok'] else ('uncertain' if result['uncertain'] else 'rejected')
    observed = gitops.remote_head(verification['path'], remote, verification['branch'])
    push_id = new_id('push')
    with conn:
        conn.execute(
            'INSERT INTO delivery_pushes (id, workspace_id, commit_id, remote, branch, upstream, '
            'status, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (push_id, workspace_id, commit_id or None, remote, verification['branch'],
             f'{remote}/{verification["branch"]}', status, result['error'], utc_now()),
        )
    if result['uncertain']:
        raise DomainError(
            'Resultado incerto: consulte o estado remoto antes de repetir. '
            + ('Remoto observado em ' + observed[:12] if observed else 'Remoto não confirmado.'),
            code='PUSH_UNCERTAIN',
            detail={'pushId': push_id, 'observedHead': observed},
        )
    if not result['ok']:
        raise DomainError(result['error'] or 'Push recusado.', code='PUSH_REJECTED',
                          detail={'pushId': push_id})
    return {
        'id': push_id, 'workspaceId': workspace_id, 'remote': remote,
        'branch': verification['branch'], 'upstream': f'{remote}/{verification["branch"]}',
        'observedHead': observed, 'status': 'pushed',
    }


def pr_preview(conn: sqlite3.Connection, workspace_id: str, base: str = '') -> dict[str, Any]:
    workspace, verification = _workspace(conn, workspace_id)
    remotes = gitops.remotes(verification['path'])
    repo = _repo_slug(remotes[0]['url']) if remotes else ''
    target = base or workspace.get('base_branch') or 'main'
    existing = github_module.get_client().find_open_pr(repo, verification['branch'], target)
    latest_commit = conn.execute(
        'SELECT * FROM delivery_commits WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1',
        (workspace_id, 'created'),
    ).fetchone()
    files = json.loads(latest_commit['files']) if latest_commit else []
    body_lines = [
        '## Resumo',
        f'Branch: {verification["branch"]} → {target}',
        f'Commit: {(latest_commit or {}).get("hash", "")[:12] or "nenhum"}',
        '',
        '## Verificações registradas',
        '- Resultados confirmados por tentativas do OpenCode e revisão de critérios.',
        '',
        '## Pendências conhecidas',
        '- Revisão final no GitHub conforme regras do repositório.',
    ]
    title = f'{verification["branch"]}: entrega do espaço'
    return {
        'workspaceId': workspace_id, 'repository': repo, 'source': verification['branch'],
        'target': target, 'title': title, 'body': '\n'.join(body_lines),
        'files': files, 'existing': existing, 'gh': github_module.get_client().detect(),
    }


def create_pr(
    conn: sqlite3.Connection,
    workspace_id: str,
    title: str,
    body: str,
    base: str,
    draft: bool = True,
    force_new: bool = False,
) -> dict[str, Any]:
    _ensure_writable()
    data = pr_preview(conn, workspace_id, base)
    if data['existing'] and not force_new:
        return {'ok': True, 'existing': True, 'pullRequest': data['existing']}
    client = github_module.get_client()
    result = client.create_pr(
        data['repository'], data['source'], data['target'],
        title or data['title'], body or data['body'], draft,
    )
    if result.get('uncertain'):
        existing = client.find_open_pr(data['repository'], data['source'], data['target'])
        raise DomainError(
            'Comunicação incerta com o GitHub. Estado remoto consultado antes de repetir.',
            code='PR_UNCERTAIN', detail={'existing': existing},
        )
    if not result['ok']:
        raise DomainError(result['error'] or 'Falha ao abrir PR.', code='PR_FAILED')
    pr_id = new_id('pr')
    now = utc_now()
    with conn:
        conn.execute(
            'INSERT INTO delivery_pull_requests (id, workspace_id, repository, source, target, '
            'draft, title, body, url, state, last_state, last_checked_at, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (pr_id, workspace_id, data['repository'], data['source'], data['target'],
             int(draft), title or data['title'], body or data['body'], result.get('url', ''),
             'open', 'open', now, now),
        )
    return {
        'ok': True, 'existing': False,
        'pullRequest': {
            'id': pr_id, 'url': result.get('url', ''), 'state': 'open',
            'source': data['source'], 'target': data['target'], 'draft': draft,
        },
    }


def refresh_pr(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    row = conn.execute(
        'SELECT * FROM delivery_pull_requests WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 1',
        (workspace_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError('Nenhum PR vinculado a este espaço.')
    data = dict(row)
    number = data.get('number')
    if not number:
        import re

        match = re.search(r'/pull/(\d+)', data.get('url') or '')
        number = int(match.group(1)) if match else None
    if not number:
        return {'ok': False, 'error': 'Número do PR indisponível para consulta.'}
    result = github_module.get_client().get_pr(data['repository'], int(number))
    if not result['ok']:
        return {'ok': False, 'error': gitops.sanitize(result['error'])}
    with conn:
        conn.execute(
            'UPDATE delivery_pull_requests SET state = ?, last_state = ?, last_checked_at = ? WHERE id = ?',
            (str(result.get('state', '')), json.dumps(result, ensure_ascii=False), utc_now(), data['id']),
        )
    return {'ok': True, 'pullRequest': result}
