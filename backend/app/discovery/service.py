"""Descoberta e abertura de projetos Git a partir de uma pasta local."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..delivery import gitops
from ..domain.errors import DomainError
from ..domain.utils import new_id, utc_now
from ..git import local as git_local
from ..git import service as git_service
from ..opencode.client import OpenCodeClient
from ..delivery import github as github_module


def _repo_slug(url: str) -> str:
    value = (url or '').strip().removesuffix('.git')
    if '://' in value:
        value = value.split('://', 1)[1]
    if '@' in value:
        value = value.split('@', 1)[1]
    if '/' in value:
        value = value.split('/', 1)[1]
    return value.replace('\\', '/')


def preferences(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = conn.execute(
        'SELECT * FROM project_discovery_preferences WHERE project_id = ?', (project_id,)
    ).fetchone()
    if row is None:
        return {
            'baseBranch': '', 'publishRemote': '', 'prRepository': '', 'prBase': '',
            'updatedAt': '', 'updatedBy': '',
        }
    data = dict(row)
    return {
        'baseBranch': data.get('base_branch') or '',
        'publishRemote': data.get('publish_remote') or '',
        'prRepository': data.get('pr_repository') or '',
        'prBase': data.get('pr_base') or '',
        'updatedAt': data.get('updated_at') or '',
        'updatedBy': data.get('updated_by') or '',
    }


def _find_project(conn: sqlite3.Connection, common_dir: str, root: str) -> dict[str, Any] | None:
    row = conn.execute(
        'SELECT * FROM projects WHERE git_common_dir = ? OR git_repo_root = ? ORDER BY created_at LIMIT 1',
        (common_dir, root),
    ).fetchone()
    return dict(row) if row else None


def preview(conn: sqlite3.Connection, path: str, github: bool = True) -> dict[str, Any]:
    """Leitura: nunca altera Git, branches, worktrees ou arquivos."""
    info = git_local.probe(path)
    if not info['ok']:
        raise DomainError(info['error'], code='INVALID_REPOSITORY', status=422)
    root = info['root']
    common_dir = info['commonDir']
    current = git_local.state(root)
    branch = current.get('branch') or ''
    worktrees = git_local.list_worktrees(root)
    remotes = gitops.remotes(root)
    upstream = gitops.upstream(root, branch) if branch else ''

    project = _find_project(conn, common_dir, root)
    saved = preferences(conn, project['id']) if project else {
        'baseBranch': '', 'publishRemote': '', 'prRepository': '', 'prBase': '',
        'updatedAt': '', 'updatedBy': '',
    }

    names = {item['name'] for item in remotes}
    publish_remote = upstream.split('/')[0] if upstream else ''
    if not publish_remote:
        publish_remote = saved['publishRemote']
    if not publish_remote and names:
        publish_remote = sorted(names)[0]

    remote_url = next((item['url'] for item in remotes if item['name'] == publish_remote), '')
    repo_slug = saved['prRepository'] or _repo_slug(remote_url)
    name = (project or {}).get('name') or repo_slug.split('/')[-1] or Path(root).name

    default_base = gitops.default_branch(root, publish_remote) if publish_remote else ''
    base_branch = saved['baseBranch'] or default_base or 'main'

    gh = github_module.get_client().detect() if github else {
        'found': False, 'authenticated': False, 'host': '', 'error': 'consulta ignorada',
    }
    existing_pr = None
    pr_base = saved['prBase']
    sources: dict[str, str] = {
        'project': 'salvo' if project else 'git',
        'branch': 'git',
        'path': 'git',
        'publishRemote': 'salvo' if saved['publishRemote'] else ('git' if publish_remote else ''),
        'baseBranch': 'salvo' if saved['baseBranch'] else ('git' if default_base else 'padrao'),
        'prBase': 'salvo' if pr_base else '',
        'openCode': 'local',
    }
    if gh.get('authenticated') and repo_slug and branch:
        try:
            found = github_module.get_client().find_open_pr(repo_slug, branch, base_branch)
            if found:
                existing_pr = {
                    'number': found.get('number'),
                    'url': found.get('url', ''),
                    'base': found.get('baseRefName') or found.get('base') or '',
                    'title': found.get('title', ''),
                }
                if found.get('baseRefName') or found.get('base'):
                    pr_base = pr_base or str(found.get('baseRefName') or found.get('base'))
                    sources['prBase'] = 'github'
        except Exception:
            pass  # GitHub indisponível: mantemos os dados locais

    if not pr_base:
        pr_base = base_branch
        sources['prBase'] = 'git' if default_base else 'padrao'

    ready = bool(branch and not current.get('detached') and branch != base_branch)
    if ready and branch == base_branch:
        ready = False
    ambiguities: list[dict[str, Any]] = []
    if len(remotes) > 1 and not saved['publishRemote']:
        ambiguities.append({
            'key': 'publishRemote',
            'reason': 'Mais de um remoto configurado.',
            'options': [item['name'] for item in remotes],
        })
    if not default_base and not saved['baseBranch']:
        ambiguities.append({
            'key': 'baseBranch',
            'reason': 'Branch-base não pôde ser determinada no remoto.',
            'options': ['main', 'master'],
        })
    if project is None and not repo_slug:
        ambiguities.append({
            'key': 'projectName',
            'reason': 'Não foi possível sugerir um nome para o projeto.',
            'options': [Path(root).name],
        })

    opencode = OpenCodeClient().detect()
    return {
        'path': root,
        'inputPath': str(Path(path).resolve()),
        'isWorktree': info['isWorktree'],
        'commonDir': common_dir,
        'projectId': (project or {}).get('id', ''),
        'projectName': name,
        'branch': branch,
        'head': current.get('head', ''),
        'detached': bool(current.get('detached')),
        'worktrees': worktrees,
        'remotes': remotes,
        'upstream': upstream,
        'publishRemote': publish_remote,
        'prRepository': repo_slug,
        'baseBranch': base_branch,
        'prBase': pr_base,
        'existingPr': existing_pr,
        'saved': saved,
        'sources': sources,
        'ambiguities': ambiguities,
        'ready': ready,
        'tools': {
            'openCode': {'found': opencode.get('found', False), 'version': opencode.get('version', '')},
            'gitHub': {'found': gh.get('found', False), 'authenticated': gh.get('authenticated', False),
                       'host': gh.get('host', ''), 'error': gh.get('error', '')},
        },
        'notes': [
            'Referência padrão do remoto pode estar desatualizada quando o GitHub está indisponível.',
            'Branch atual, upstream e base do PR são informações distintas.',
        ],
    }


def open_project(
    conn: sqlite3.Connection, path: str, choices: dict[str, Any] | None = None
) -> dict[str, Any]:
    choices = choices or {}
    data = preview(conn, path, github=bool(choices.get('github', True)))
    root = data['path']
    common_dir = data['commonDir']
    branch = data['branch']
    now = utc_now()

    publish_remote = choices.get('publishRemote') or data['publishRemote']
    base_branch = choices.get('baseBranch') or data['baseBranch']
    pr_base = choices.get('prBase') or data['prBase']
    pr_repository = choices.get('prRepository') or data['prRepository']
    project_name = choices.get('projectName') or data['projectName']

    project = _find_project(conn, common_dir, root)
    reused_project = project is not None
    with conn:
        if project is None:
            project_id = new_id('prj')
            conn.execute(
                'INSERT INTO projects (id, name, objective, rules, base_branch, repo_path, '
                'git_repo_root, git_common_dir, git_linked_at, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (project_id, project_name, '', '', base_branch, root, root, common_dir, now, now, now),
            )
        else:
            project_id = project['id']
            conn.execute('UPDATE projects SET git_repo_root = ?, git_common_dir = ?, updated_at = ? WHERE id = ?',
                         (root, common_dir, now, project_id))
        conn.execute(
            'INSERT INTO project_discovery_preferences (project_id, base_branch, publish_remote, '
            'pr_repository, pr_base, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(project_id) DO UPDATE SET base_branch = excluded.base_branch, '
            'publish_remote = excluded.publish_remote, pr_repository = excluded.pr_repository, '
            'pr_base = excluded.pr_base, updated_at = excluded.updated_at, updated_by = excluded.updated_by',
            (project_id, base_branch, publish_remote, pr_repository, pr_base, now, 'usuario'),
        )

    workspace = conn.execute(
        'SELECT * FROM workspaces WHERE project_id = ? AND git_work_dir = ? AND git_branch = ? '
        'ORDER BY created_at LIMIT 1',
        (project_id, root, branch),
    ).fetchone()
    reused_workspace = workspace is not None
    now = utc_now()
    with conn:
        if workspace is None:
            workspace_id = new_id('ws')
            conn.execute(
                'INSERT INTO workspaces (id, project_id, name, branch, base_branch, work_dir, kind, '
                'git_status, git_repo_root, git_common_dir, git_work_dir, git_branch, bound_head, '
                'git_linked_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (workspace_id, project_id, project_name, branch, base_branch, root, 'worktree',
                 'ready', root, common_dir, root, branch, data['head'], now, now, now),
            )
            conn.execute(
                'INSERT INTO conversations (id, workspace_id, title, created_at) VALUES (?, ?, ?, ?)',
                (new_id('conv'), workspace_id, 'Conversa', now),
            )
        else:
            workspace_id = workspace['id']
            conn.execute(
                'UPDATE workspaces SET git_status = ?, git_repo_root = ?, git_common_dir = ?, '
                'git_work_dir = ?, git_branch = ?, bound_head = ?, updated_at = ? WHERE id = ?',
                ('ready', root, common_dir, root, branch, data['head'], now, workspace_id),
            )
        conn.execute(
            'INSERT INTO workspace_discovery (workspace_id, root, common_dir, observed_head, source, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(workspace_id) DO UPDATE SET root = excluded.root, '
            'common_dir = excluded.common_dir, observed_head = excluded.observed_head, '
            'source = excluded.source, updated_at = excluded.updated_at',
            (workspace_id, root, common_dir, data['head'], 'local', now),
        )

    result = dict(data)
    result.update({
        'projectId': project_id,
        'workspaceId': workspace_id,
        'reusedProject': reused_project,
        'reusedWorkspace': reused_workspace,
        'baseBranch': base_branch,
        'publishRemote': publish_remote,
        'prBase': pr_base,
        'prRepository': pr_repository,
        'projectName': project_name,
    })
    return result
