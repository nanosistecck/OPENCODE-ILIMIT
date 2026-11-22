"""Integração com GitHub CLI (gh). Adaptador de teste pode ser injetado."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from .gitops import sanitize


class GitHubClient:
    def __init__(self, executable: str = '') -> None:
        self.executable = executable or shutil.which('gh') or ''

    def detect(self) -> dict[str, Any]:
        if not self.executable:
            return {
                'found': False, 'path': '', 'version': '', 'authenticated': False,
                'host': '', 'error': 'GitHub CLI (gh) não está instalado neste computador.',
            }
        result = self._run(['--version'])
        auth = self._run(['auth', 'status'])
        host = ''
        text = auth.get('stdout', '') + auth.get('stderr', '')
        for line in text.splitlines():
            if 'Logged in to' in line or 'github.com' in line:
                host = 'github.com'
                break
        return {
            'found': True,
            'path': self.executable,
            'version': result.get('stdout', '').splitlines()[0] if result.get('ok') else '',
            'authenticated': bool(auth.get('ok')),
            'host': host,
            'error': sanitize(auth.get('error', '')),
        }

    def _run(self, args: list[str], timeout: int = 30) -> dict[str, Any]:
        try:
            process = subprocess.run(
                [self.executable, *args], capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'ok': False, 'stdout': '', 'stderr': '', 'error': sanitize(str(exc))}
        return {
            'ok': process.returncode == 0,
            'stdout': process.stdout[:50_000],
            'stderr': process.stderr[:10_000],
            'error': sanitize(process.stderr.strip() or process.stdout.strip()),
        }

    def find_open_pr(self, repository: str, source: str, target: str) -> dict[str, Any] | None:
        if not repository:
            return None
        result = self._run([
            'pr', 'list', '--repo', repository, '--head', source, '--base', target,
            '--state', 'open', '--limit', '1',
            '--json', 'number,url,state,isDraft,title,headRefName,baseRefName',
        ])
        if not result['ok']:
            return None
        try:
            items = json.loads(result['stdout'] or '[]')
            return items[0] if items else None
        except json.JSONDecodeError:
            return None

    def create_pr(
        self, repository: str, source: str, target: str,
        title: str, body: str, draft: bool = True,
    ) -> dict[str, Any]:
        args = [
            'pr', 'create',
            *(['--repo', repository] if repository else []),
            '--head', source, '--base', target,
            '--title', title, '--body', body,
        ]
        if draft:
            args.append('--draft')
        result = self._run(args, timeout=60)
        if not result['ok']:
            return {'ok': False, 'error': result['error'], 'uncertain': 'timeout' in result['error'].lower()}
        return {'ok': True, 'url': result['stdout'].strip().splitlines()[-1] if result['stdout'].strip() else '',
                'error': '', 'uncertain': False}

    def get_pr(self, repository: str, number: int) -> dict[str, Any]:
        result = self._run([
            'pr', 'view', str(number),
            *(['--repo', repository] if repository else []),
            '--json', 'number,url,state,isDraft,title,body,headRefName,baseRefName,statusCheckRollup',
        ])
        if not result['ok']:
            return {'ok': False, 'error': result['error']}
        try:
            return {'ok': True, **json.loads(result['stdout'] or '{}')}
        except json.JSONDecodeError:
            return {'ok': False, 'error': 'Resposta inválida do gh.'}


def get_client() -> GitHubClient:
    return GitHubClient()
