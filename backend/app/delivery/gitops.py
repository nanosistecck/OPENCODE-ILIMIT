"""Comandos Git de escrita e consulta — argumentos separados, nunca shell."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..git.runner import run_git

_URL_SECRET = re.compile(r"(https?://)([^/\s:@]+):([^@/\s]+)@")
_KV_SECRET = re.compile(r"(?i:token|password|secret|authorization)([\"'\s:=]+)([^\s\"',]+)")


def sanitize(value: str) -> str:
    """Remove credenciais antes de mostrar erros ou URLs no painel."""
    if not value:
        return value
    result = _URL_SECRET.sub(r'\1***:***@', value)
    result = _KV_SECRET.sub(lambda m: m.group(1) + '***', result)
    return result[:4000]


def validate_path(workspace_path: str | Path, file_path: str) -> Path | None:
    base = Path(workspace_path).resolve()
    candidate = Path(file_path)
    if candidate.is_absolute():
        return None
    target = (base / candidate).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    return target


def remotes(path: str | Path) -> list[dict[str, str]]:
    """Um registro por remoto: `git remote -v` repete cada nome para fetch e push."""
    result = run_git(['-C', str(path), 'remote', '-v'])
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] not in seen:
            seen.add(parts[0])
            items.append({'name': parts[0], 'url': sanitize(parts[1]), 'direction': parts[2].strip('()')})
    return items


def upstream(path: str | Path, branch: str) -> str:
    result = run_git(['-C', str(path), 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'])
    return result.text if result.ok else ''


def ahead_count(path: str | Path, remote: str, branch: str) -> int | None:
    ref = f'{remote}/{branch}'
    exists = run_git(['-C', str(path), 'rev-parse', '--verify', ref])
    if not exists.ok:
        return None
    result = run_git(['-C', str(path), 'rev-list', '--count', f'{ref}..HEAD'])
    return int(result.text) if result.ok and result.text.isdigit() else None


def default_branch(path: str | Path, remote: str) -> str:
    """Branch padrão conhecida localmente para o remoto (pode estar desatualizada)."""
    result = run_git(['-C', str(path), 'symbolic-ref', '--quiet', f'refs/remotes/{remote}/HEAD'])
    if result.ok and result.text:
        return result.text.rsplit('/', 1)[-1]
    for name in ('main', 'master'):
        exists = run_git(['-C', str(path), 'rev-parse', '--verify', f'refs/remotes/{remote}/{name}'])
        if exists.ok:
            return name
    return ''


def staged_files(path: str | Path) -> list[str]:
    result = run_git(['-C', str(path), 'diff', '--cached', '--name-only', '-z'])
    return [item for item in result.stdout.split('\0') if item]


def index_digest(path: str | Path) -> str:
    """Conteúdo do índice + HEAD: detecta mudanças externas após a prévia."""
    import hashlib

    head = run_git(['-C', str(path), 'rev-parse', 'HEAD']).stdout
    staged = run_git(['-C', str(path), 'diff', '--cached', '--raw', '-z']).stdout
    files = run_git(['-C', str(path), 'status', '--porcelain=v1', '-z', '--untracked-files=all']).stdout
    diff_uncached = run_git(['-C', str(path), 'diff', '--no-ext-diff']).stdout
    diff_cached = run_git(['-C', str(path), 'diff', '--cached', '--no-ext-diff']).stdout

    # Arquivos novos aparecem no status apenas pelo nome: incluir o conteúdo detecta edições externas.
    untracked_digest = ''
    base = Path(path).resolve()
    for record in files.split('\0'):
        if not record or not record.startswith('??'):
            continue
        target = base / record[3:]
        if target.is_file():
            try:
                untracked_digest += hashlib.sha256(target.read_bytes()[:1_000_000]).hexdigest()
            except OSError:
                pass

    payload = head + '\0' + staged + '\0' + files + '\0' + diff_uncached + '\0' + diff_cached + '\0' + untracked_digest
    return hashlib.sha256(payload.encode('utf-8', errors='replace')).hexdigest()


def stage(path: str | Path, file_paths: list[str]) -> tuple[bool, str]:
    for file_path in file_paths:
        if validate_path(path, file_path) is None:
            return False, f'Caminho inválido: {file_path}'
    if not file_paths:
        return True, ''
    result = run_git(['-C', str(path), 'add', '--', *file_paths])
    return result.ok, sanitize(result.error)


def commit(path: str | Path, message: str) -> tuple[bool, str]:
    message = (message or '').strip()
    if not message:
        return False, 'Mensagem de commit é obrigatória.'
    result = run_git(['-C', str(path), 'commit', '-m', message], timeout=60)
    return result.ok, sanitize(result.error)


def push(path: str | Path, remote: str, branch: str, set_upstream: bool = True) -> dict[str, Any]:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', remote or ''):
        return {'ok': False, 'error': 'Nome de remoto inválido.', 'uncertain': False}
    args = ['-C', str(path), 'push']
    if set_upstream:
        args.append('-u')
    args += [remote, branch]
    result = run_git(args, timeout=90)
    uncertain = result.returncode == -2 or (not result.ok and 'timeout' in result.error.lower())
    return {'ok': result.ok, 'error': sanitize(result.error), 'uncertain': uncertain}


def remote_head(path: str | Path, remote: str, branch: str) -> str:
    result = run_git(['-C', str(path), 'ls-remote', remote, f'refs/heads/{branch}'], timeout=30)
    if not result.ok or not result.stdout.strip():
        return ''
    return result.stdout.split()[0]
