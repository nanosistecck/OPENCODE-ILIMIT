"""ConsultasGit reutilizáveis: repositório, refs, worktrees, status e diff."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..config import settings
from .runner import run_git

_STATUS_NAMES = {
    ' ': 'none', '?': 'untracked', '!': 'ignored', 'A': 'added', 'M': 'modified',
    'D': 'deleted', 'R': 'renamed', 'C': 'copied', 'U': 'conflict', 'T': 'type_changed',
}
_CONFLICTS = {'DD', 'AA', 'AU', 'UA', 'DU', 'UD', 'UU'}


def normalize_path(value: str | Path) -> str:
    """Comparação estável entre caminhos no Windows (separadores e caixa)."""
    return str(Path(value).resolve()).replace('\\', '/').lower()


def probe(path: str | Path) -> dict[str, Any]:
    """Resolve uma subpasta para a raiz e identifica o repositório comum."""
    target = Path(path).expanduser()
    if not target.exists():
        return {'ok': False, 'error': f'Caminho não existe nesta máquina: {target}'}
    root_result = run_git(['-C', str(target), 'rev-parse', '--show-toplevel'])
    if not root_result.ok:
        return {'ok': False, 'error': root_result.error or 'Não é um repositório Git.'}
    root = Path(root_result.text).resolve()
    common_result = run_git(['-C', str(root), 'rev-parse', '--git-common-dir'])
    if not common_result.ok:
        return {'ok': False, 'error': common_result.error}
    common = Path(common_result.text)
    if not common.is_absolute():
        common = (root / common).resolve()
    return {
        'ok': True,
        'root': str(root),
        'commonDir': str(common.resolve()),
        'commonId': normalize_path(common),
        'isWorktree': normalize_path(common) != normalize_path(root / '.git'),
        'error': '',
    }


def state(path: str | Path) -> dict[str, Any]:
    branch = run_git(['-C', str(path), 'symbolic-ref', '--short', '-q', 'HEAD'])
    head = run_git(['-C', str(path), 'rev-parse', 'HEAD'])
    abbreviated = run_git(['-C', str(path), 'rev-parse', '--abbrev-ref', 'HEAD'])
    detached = not branch.ok or abbreviated.text == 'HEAD'
    return {
        'branch': '' if detached else branch.text,
        'head': head.text if head.ok else '',
        'detached': detached,
        'hasCommits': head.ok,
    }


def refs(root: str | Path) -> dict[str, Any]:
    result = run_git([
        '-C', str(root), 'for-each-ref',
        '--format=%(refname)%09%(objectname)%09%(subject)',
        'refs/heads', 'refs/remotes',
    ])
    local: list[dict[str, Any]] = []
    remote: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 2)
        if len(parts) < 2:
            continue
        ref, commit = parts[0], parts[1]
        subject = parts[2] if len(parts) > 2 else ''
        entry = {'ref': ref, 'commit': commit, 'subject': subject}
        if ref.startswith('refs/heads/'):
            entry['name'] = ref[len('refs/heads/'):]
            entry['kind'] = 'local'
            local.append(entry)
        elif ref.startswith('refs/remotes/') and not ref.endswith('/HEAD'):
            entry['name'] = ref[len('refs/remotes/'):]
            entry['kind'] = 'remote'
            remote.append(entry)

    def suggestion(name: str) -> dict[str, Any] | None:
        local_ref = next((item for item in local if item['name'] == name), None)
        remote_ref = next((item for item in remote if item['name'].endswith('/' + name)), None)
        if local_ref and remote_ref and local_ref['commit'] != remote_ref['commit']:
            return {
                'name': name,
                'options': [
                    {**local_ref, 'label': f'local {name}'},
                    {**remote_ref, 'label': f'{remote_ref["name"]} (remoto)'},
                ],
            }
        chosen = local_ref or remote_ref
        return {'name': name, 'options': [chosen]} if chosen else None

    suggestions = [item for item in (suggestion('main'), suggestion('master')) if item]
    if not suggestions:
        first = local[0] if local else (remote[0] if remote else None)
        if first:
            suggestions = [{'name': first['name'], 'options': [first]}]
    return {'local': local, 'remote': remote, 'suggestions': suggestions}


def list_worktrees(root: str | Path) -> list[dict[str, Any]]:
    result = run_git(['-C', str(root), 'worktree', 'list', '--porcelain'])
    items: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            if current:
                items.append(current)
                current = {}
            continue
        key, _, value = line.partition(' ')
        if key == 'worktree':
            current = {'path': value, 'head': '', 'branch': '', 'detached': False, 'locked': False}
        elif key in ('HEAD', 'head'):
            current['head'] = value
        elif key == 'branch':
            current['branch'] = value.removeprefix('refs/heads/')
        elif key in ('detached', 'bare'):
            current['detached'] = True
        elif key == 'locked':
            current['locked'] = True
    if current:
        items.append(current)
    return items


def check_branch_name(name: str) -> tuple[bool, str]:
    result = run_git(['check-ref-format', '--branch', name])
    return result.ok, result.error


def branch_exists(root: str | Path, name: str) -> bool:
    return run_git(['-C', str(root), 'show-ref', '--verify', '--quiet', f'refs/heads/{name}']).ok


def branch_in_worktree(root: str | Path, name: str) -> dict[str, Any] | None:
    return next((item for item in list_worktrees(root) if item.get('branch') == name), None)


def safe_folder_name(branch: str) -> str:
    """Nome válido no Windows e sem depender de barras na branch."""
    cleaned = ''.join(char if char not in '<>:"/\\|?*' else '-' for char in branch.strip())
    cleaned = cleaned.replace('/', '-').replace('\\', '-').strip(' .-')
    return cleaned[:120] or 'worktree'


def operations_in_progress(path: str | Path, common_dir: str | Path) -> list[str]:
    markers = [
        ('MERGE_HEAD', 'merge'), ('REBASE_HEAD', 'rebase'),
        ('rebase-merge', 'rebase'), ('rebase-apply', 'rebase'),
        ('CHERRY_PICK_HEAD', 'cherry-pick'), ('REVERT_HEAD', 'revert'),
        ('BISECT_LOG', 'bisect'),
    ]
    base = Path(common_dir)
    return [label for name, label in markers if (base / name).exists()]


def _numstat_binary(path: str | Path, staged: bool) -> set[str]:
    args = ['-C', str(path), 'diff', '--numstat']
    if staged:
        args.append('--cached')
    result = run_git(args)
    binaries: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split('\t', 2)
        if len(parts) == 3 and parts[0] == '-' and parts[1] == '-':
            binaries.add(parts[2])
    return binaries


def status(path: str | Path, common_dir: str | Path) -> dict[str, Any]:
    result = run_git(['-C', str(path), 'status', '--porcelain=v1', '-z', '--untracked-files=all'])
    if not result.ok:
        return {'ok': False, 'error': result.error, 'files': [], 'summary': {}}

    tokens = result.stdout.split('\0')
    files: list[dict[str, Any]] = []
    index = 0
    binaries = _numstat_binary(path, False) | _numstat_binary(path, True)
    while index < len(tokens):
        record = tokens[index]
        index += 1
        if not record:
            continue
        xy = record[:2]
        file_path = record[3:]
        old_path = ''
        if 'R' in xy or 'C' in xy:
            old_path = file_path
            if index < len(tokens):
                file_path = tokens[index]
                index += 1
        x, y = xy[0], xy[1]
        conflict = xy in _CONFLICTS or 'U' in xy
        files.append({
            'path': file_path,
            'oldPath': old_path,
            'indexStatus': _STATUS_NAMES.get(x, 'modified'),
            'worktreeStatus': _STATUS_NAMES.get(y, 'modified'),
            'staged': x not in (' ', '?', '!') and x != '',
            'unstaged': y not in (' ', '!') and y != '',
            'untracked': x == '?',
            'conflict': conflict,
            'binary': file_path in binaries,
        })

    summary = {
        'total': len(files),
        'staged': sum(1 for item in files if item['staged']),
        'unstaged': sum(1 for item in files if item['unstaged']),
        'untracked': sum(1 for item in files if item['untracked']),
        'conflicts': sum(1 for item in files if item['conflict']),
    }
    return {
        'ok': True,
        'files': files,
        'summary': summary,
        'operations': operations_in_progress(path, common_dir),
        'head': state(path)['head'],
        'branch': state(path)['branch'],
        'error': '',
    }


def file_diff(
    workspace_path: str | Path,
    file_path: str,
    staged: bool,
    untracked: bool = False,
) -> dict[str, Any]:
    """Só aceita arquivos dentro da pasta do espaço; saída textual limitada."""
    base = Path(workspace_path).resolve()
    candidate = Path(file_path)
    if candidate.is_absolute():
        return {'available': False, 'reason': 'Caminho absoluto não é permitido.'}
    target = (base / candidate).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {'available': False, 'reason': 'Arquivo fora da pasta do espaço.'}
    if target.is_dir():
        return {'available': False, 'reason': 'Caminho é um diretório.'}

    if untracked:
        try:
            raw = target.read_bytes()[: settings.max_diff_chars]
            text = raw.decode('utf-8', errors='replace')
        except OSError as exc:
            return {'available': False, 'reason': f'Não foi possível ler o arquivo: {exc}'}
        return {
            'available': True, 'text': text, 'binary': b'\x00' in raw,
            'truncated': target.stat().st_size > settings.max_diff_chars,
            'reason': 'Prévia de arquivo ainda não rastreado.',
        }

    numstat = run_git([
        '-C', str(base), 'diff', '--numstat', *( ['--cached'] if staged else [] ), '--', file_path,
    ])
    binary = any(
        len(parts) == 3 and parts[0] == '-' and parts[1] == '-'
        for parts in (line.split('\t', 2) for line in numstat.stdout.splitlines())
    )
    if binary:
        return {'available': False, 'binary': True, 'reason': 'Arquivo binário: prévia textual indisponível.'}

    result = run_git([
        '-C', str(base), 'diff', '--no-ext-diff', '--unified=3',
        *( ['--cached'] if staged else [] ), '--', file_path,
    ])
    if not result.ok:
        return {'available': False, 'reason': result.error}
    full = result.stdout
    truncated = len(full) > settings.max_diff_chars
    return {
        'available': True,
        'text': full[: settings.max_diff_chars],
        'binary': False,
        'truncated': truncated,
        'reason': 'Prévia truncada.' if truncated else '',
    }


def verify_binding(workspace: dict[str, Any]) -> dict[str, Any]:
    """Operação reutilizável: pasta, branch, HEAD e motivo de indisponibilidade."""
    reasons: list[str] = []
    path = workspace.get('git_work_dir') or workspace.get('work_dir') or ''
    expected_branch = workspace.get('git_branch') or workspace.get('branch') or ''
    target = Path(path).expanduser() if path else None
    current: dict[str, Any] = {'branch': '', 'head': '', 'detached': False}

    if not target or not target.exists():
        reasons.append('MISSING_PATH')
    else:
        info = probe(target)
        if not info['ok']:
            reasons.append('INVALID_REPOSITORY')
        else:
            expected_common = workspace.get('git_common_dir')
            if expected_common and normalize_path(info['commonDir']) != normalize_path(expected_common):
                reasons.append('WRONG_REPOSITORY')
            current = state(target)
            if current['detached']:
                reasons.append('DETACHED_HEAD')
            elif expected_branch and current['branch'] != expected_branch:
                reasons.append('BRANCH_CHANGED')
            st = status(target, info['commonDir'])
            if st.get('operations'):
                reasons.append('OPERATION_IN_PROGRESS')
            if st.get('summary', {}).get('conflicts', 0) > 0:
                reasons.append('CONFLICTS')
            current['status'] = st.get('summary', {})
            current['operations'] = st.get('operations', [])

    if workspace.get('git_status') != 'ready':
        reasons.append('LINK_PENDING')

    return {
        'workspaceId': workspace['id'],
        'path': path,
        'branch': expected_branch,
        'observedBranch': current.get('branch', ''),
        'head': current.get('head', ''),
        'boundHead': workspace.get('bound_head') or '',
        'originCommit': workspace.get('origin_commit') or '',
        'ready': not reasons,
        'reasons': reasons,
        'localChanges': current.get('status', {}),
        'operations': current.get('operations', []),
    }
