"""Serviço Git + SQLite. Regras de vínculo fora das rotas, reutilizáveis pelo motor."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..config import settings
from ..domain import projects as project_rules
from ..domain.errors import DomainError, NotFoundError
from ..domain.utils import utc_now
from . import local
from .runner import run_git

_locks: dict[tuple[str, str], threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(branch: str, path: str) -> threading.Lock:
    key = (branch.strip().lower(), local.normalize_path(path))
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _require_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    project = project_rules.get_project(conn, project_id)
    if not project.get('git_repo_root'):
        raise DomainError('Projeto ainda não tem repositório vinculado.', code='REPO_NOT_LINKED')
    return project


def _commit_of(root: str, ref: str) -> str:
    result = run_git(['-C', root, 'rev-parse', '--verify', f'{ref}^{{commit}}'])
    if not result.ok:
        raise DomainError(
            f'Referência sem commit disponível: {ref}. Não é possível criar um espaço a partir de uma base vazia.',
            code='BASE_WITHOUT_COMMITS', status=422,
        )
    return result.text


def probe_repository(path: str) -> dict[str, Any]:
    info = local.probe(path)
    if not info['ok']:
        return info
    info['state'] = local.state(info['root'])
    info['refs'] = local.refs(info['root'])
    return info


def link_repository(conn: sqlite3.Connection, project_id: str, path: str) -> dict[str, Any]:
    project_rules.get_project(conn, project_id)
    info = probe_repository(path)
    if not info['ok']:
        raise DomainError(info['error'], code='INVALID_REPOSITORY', status=422)
    with conn:
        conn.execute(
            'UPDATE projects SET git_repo_root = ?, git_common_dir = ?, git_linked_at = ?, updated_at = ? '
            'WHERE id = ?',
            (info['root'], info['commonDir'], utc_now(), utc_now(), project_id),
        )
    return overview(conn, project_id)


def overview(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    project = _require_project(conn, project_id)
    root = project['git_repo_root']
    info = local.probe(root)
    if not info['ok']:
        raise DomainError(info['error'], code='INVALID_REPOSITORY', status=422)
    return {
        'projectId': project_id,
        'root': info['root'],
        'commonDir': info['commonDir'],
        'state': local.state(info['root']),
        'refs': local.refs(info['root']),
        'worktrees': local.list_worktrees(info['root']),
    }


def target_path_for(branch: str) -> Path:
    return settings.worktrees_dir / local.safe_folder_name(branch)


def _verify_created(path: Path, common_dir: str, branch: str) -> dict[str, Any]:
    info = local.probe(path)
    current = local.state(path) if info['ok'] else {}
    valid = (
        info['ok']
        and local.normalize_path(info['commonDir']) == local.normalize_path(common_dir)
        and current.get('branch') == branch
        and bool(current.get('head'))
    )
    if not valid:
        raise DomainError(
            f'A worktree foi criada em {path}, mas a verificação falhou. É possível vincular a pasta existente.',
            code='VERIFICATION_FAILED',
            detail={'worktreeCreated': True, 'path': str(path), 'branch': branch},
        )
    return {'path': str(path), 'head': current['head'], 'root': info['root'], 'commonDir': info['commonDir']}


def _persist_binding(
    conn: sqlite3.Connection,
    workspace_id: str,
    *,
    root: str,
    common_dir: str,
    path: str,
    branch: str,
    base_ref: str,
    origin_commit: str,
    bound_head: str,
) -> None:
    try:
        with conn:
            conn.execute(
                'UPDATE workspaces SET git_status = ?, git_repo_root = ?, git_common_dir = ?, '
                'git_work_dir = ?, git_branch = ?, base_ref = ?, origin_commit = ?, bound_head = ?, '
                'git_linked_at = ?, git_error = NULL, updated_at = ? WHERE id = ?',
                ('ready', root, common_dir, path, branch, base_ref, origin_commit, bound_head,
                 utc_now(), utc_now(), workspace_id),
            )
    except Exception as exc:  # Git já foi executado; não apagar a worktree criada.
        raise DomainError(
            f'A worktree existe em {path}, mas o banco falhou. Tente vincular a pasta existente.',
            code='WORKTREE_CREATED_DB_FAILED',
            detail={'worktreeCreated': True, 'path': path, 'branch': branch, 'reason': str(exc)},
        ) from exc


def create_branch_workspace(conn: sqlite3.Connection, workspace_id: str, branch: str, start_ref: str) -> dict[str, Any]:
    workspace, project = _require_project_workspace(conn, workspace_id)
    valid, message = local.check_branch_name(branch)
    if not valid:
        raise DomainError(f'Nome de branch inválido: {message}', code='INVALID_BRANCH', status=422)
    if local.branch_exists(project['git_repo_root'], branch):
        raise DomainError('Branch já existe localmente.', code='BRANCH_CONFLICT')
    target = target_path_for(branch)
    if target.exists():
        raise DomainError(f'Pasta de destino já existe: {target}', code='PATH_CONFLICT')

    with _lock_for(branch, str(target)):
        origin_commit = _commit_of(project['git_repo_root'], start_ref)
        result = run_git([
            '-C', project['git_repo_root'], 'worktree', 'add',
            '-b', branch, str(target), start_ref,
        ])
        if not result.ok:
            raise DomainError(f'Falha ao criar worktree: {result.error}', code='GIT_FAILED')
        verified = _verify_created(target, project['git_common_dir'], branch)
        _persist_binding(
            conn, workspace_id,
            root=verified['root'], common_dir=verified['commonDir'], path=str(target),
            branch=branch, base_ref=start_ref, origin_commit=origin_commit,
            bound_head=verified['head'],
        )
    return status_payload(conn, workspace_id)


def open_workspace(
    conn: sqlite3.Connection,
    workspace_id: str,
    action: str,
    *,
    path: str = '',
    source_ref: str = '',
    branch: str = '',
) -> dict[str, Any]:
    """Ações: link (pasta existente), attach (branch local livre), remote (criar branch local)."""
    workspace, project = _require_project_workspace(conn, workspace_id)
    branch = branch or workspace.get('git_branch') or workspace['branch']
    expected_common = project['git_common_dir']

    if action == 'link':
        if not path:
            raise DomainError('Informe a pasta da worktree.', code='VALIDATION', status=422)
        target = Path(path).expanduser()
        info = local.probe(target)
        if not info['ok']:
            raise DomainError(info['error'], code='INVALID_REPOSITORY', status=422)
        if local.normalize_path(info['commonDir']) != local.normalize_path(expected_common):
            raise DomainError('A pasta pertence a outro repositório.', code='WRONG_REPOSITORY')
        current = local.state(target)
        if current['detached']:
            raise DomainError('A worktree está com HEAD destacado.', code='DETACHED_HEAD')
        if current['branch'] != branch:
            raise DomainError(
                f'Branch observada ({current["branch"]}) difere da cadastrada ({branch}).',
                code='BRANCH_CHANGED',
            )
        _persist_binding(
            conn, workspace_id,
            root=info['root'], common_dir=info['commonDir'], path=str(target.resolve()),
            branch=branch, base_ref=workspace.get('base_ref') or '',
            origin_commit=workspace.get('origin_commit') or current['head'],
            bound_head=current['head'],
        )
        return status_payload(conn, workspace_id)

    valid, message = local.check_branch_name(branch)
    if not valid:
        raise DomainError(f'Nome de branch inválido: {message}', code='INVALID_BRANCH', status=422)
    target = target_path_for(branch)

    with _lock_for(branch, str(target)):
        if action == 'remote':
            if not source_ref:
                raise DomainError('Selecione a referência remota de origem.', code='VALIDATION', status=422)
            origin_commit = _commit_of(project['git_repo_root'], source_ref)
            if not local.branch_exists(project['git_repo_root'], branch):
                created = run_git(['-C', project['git_repo_root'], 'branch', branch, source_ref])
                if not created.ok:
                    raise DomainError(f'Falha ao criar branch local: {created.error}', code='GIT_FAILED')
        elif action == 'attach':
            if not local.branch_exists(project['git_repo_root'], branch):
                raise DomainError('Branch local não existe.', code='BRANCH_NOT_FOUND')
            origin_commit = _commit_of(project['git_repo_root'], f'refs/heads/{branch}')
        else:
            raise DomainError('Ação desconhecida.', code='VALIDATION', status=422)

        if local.branch_in_worktree(project['git_repo_root'], branch):
            raise DomainError('Branch já está em uma worktree; use "vincular pasta existente".', code='BRANCH_CONFLICT')
        if target.exists():
            raise DomainError(f'Pasta de destino já existe: {target}', code='PATH_CONFLICT')

        added = run_git(['-C', project['git_repo_root'], 'worktree', 'add', str(target), branch])
        if not added.ok:
            raise DomainError(f'Falha ao criar worktree: {added.error}', code='GIT_FAILED')
        verified = _verify_created(target, expected_common, branch)
        _persist_binding(
            conn, workspace_id,
            root=verified['root'], common_dir=verified['commonDir'], path=str(target),
            branch=branch, base_ref=source_ref or f'refs/heads/{branch}',
            origin_commit=origin_commit, bound_head=verified['head'],
        )
    return status_payload(conn, workspace_id)


def _require_project_workspace(conn: sqlite3.Connection, workspace_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace = project_rules.get_workspace(conn, workspace_id)
    project = project_rules.get_project(conn, workspace['project_id'])
    if not project.get('git_repo_root'):
        raise DomainError('Projeto ainda não tem repositório vinculado.', code='REPO_NOT_LINKED')
    return workspace, project


def status_payload(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    workspace, project = _require_project_workspace(conn, workspace_id)
    path = workspace.get('git_work_dir')
    if not path or not Path(path).exists():
        return {
            'workspaceId': workspace_id, 'available': False, 'reason': 'MISSING_PATH',
            'path': path or '', 'files': [], 'summary': {}, 'operations': [],
        }
    info = local.probe(path)
    if not info['ok']:
        return {
            'workspaceId': workspace_id, 'available': False, 'reason': 'INVALID_REPOSITORY',
            'path': path, 'files': [], 'summary': {}, 'operations': [],
        }
    result = local.status(path, info['commonDir'])
    result['workspaceId'] = workspace_id
    result['path'] = str(Path(path).resolve())
    result['available'] = result.get('ok', False)
    result.pop('ok', None)
    result.setdefault('operations', [])
    return result


def diff_payload(
    conn: sqlite3.Connection, workspace_id: str, file_path: str, staged: bool, untracked: bool
) -> dict[str, Any]:
    workspace, _ = _require_project_workspace(conn, workspace_id)
    path = workspace.get('git_work_dir')
    if not path or not Path(path).exists():
        raise DomainError('Pasta do espaço não existe.', code='MISSING_PATH')
    result = local.file_diff(path, file_path, staged, untracked)
    return {'workspaceId': workspace_id, 'file': file_path, 'staged': staged, **result}


def verify(conn: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    workspace, _ = _require_project_workspace(conn, workspace_id)
    return local.verify_binding(workspace)
