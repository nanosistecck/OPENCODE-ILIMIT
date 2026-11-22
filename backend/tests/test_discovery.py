from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.delivery import github as github_module
from app.domain.utils import new_id
from app.remote.state import set_remote_active

PR = {'number': 42, 'url': 'https://github.com/acme/repo/pull/42',
      'baseRefName': 'develop', 'title': 'PR aberto', 'state': 'open', 'isDraft': True}


class FakeGitHub:
    def __init__(self, authenticated=True, pr=None):
        self.authenticated = authenticated
        self.pr = pr

    def detect(self):
        return {'found': True, 'path': 'fake-gh', 'version': 'gh test',
                'authenticated': self.authenticated, 'host': 'github.com', 'error': ''}

    def find_open_pr(self, repository, source, target):
        return self.pr if self.authenticated else None


@pytest.fixture(autouse=True)
def fake_gh(monkeypatch):
    monkeypatch.setattr(github_module, 'get_client', lambda: FakeGitHub(pr=PR))
    set_remote_active(False)
    yield
    set_remote_active(False)


def make_repo(git_repo):
    root = git_repo['root']
    branch = f'feat/desc-{new_id("b")[:8]}'
    worktree = root.parent / f'wt-{branch.split("/")[-1]}'
    git_repo['git']('worktree', 'add', '-b', branch, str(worktree), 'main')
    return root, branch, worktree


def test_subpasta_e_reabertura(client: TestClient, git_repo) -> None:
    _, branch, worktree = make_repo(git_repo)
    subfolder = worktree / 'docs' / 'detalhes'
    subfolder.mkdir(parents=True)

    preview = client.post('/api/discovery/preview', json={'path': str(subfolder)}).json()
    assert Path(preview['path']).resolve() == worktree.resolve()
    assert preview['branch'] == branch

    opened = client.post('/api/discovery/open', json={'path': str(subfolder)}).json()
    assert opened['workspaceId']
    assert opened['reusedWorkspace'] is False

    again = client.post('/api/discovery/open', json={'path': str(worktree)}).json()
    assert again['workspaceId'] == opened['workspaceId']
    assert again['reusedWorkspace'] is True
    assert again['projectId'] == opened['projectId']

    state = client.get(f"/api/workspaces/{opened['workspaceId']}/state").json()
    assert state['git']['branch'] == branch


def test_duas_worktrees_mesmo_projeto(client: TestClient, git_repo) -> None:
    _, branch_a, wt_a = make_repo(git_repo)
    _, branch_b, wt_b = make_repo(git_repo)
    first = client.post('/api/discovery/open', json={'path': str(wt_a)}).json()
    second = client.post('/api/discovery/open', json={'path': str(wt_b)}).json()
    assert first['projectId'] == second['projectId']
    assert first['workspaceId'] != second['workspaceId']
    assert first['branch'] == branch_a
    assert second['branch'] == branch_b


def test_fork_publicacao_e_base_pr_distintas(client: TestClient, git_repo) -> None:
    root = git_repo['root']
    git_repo['git']('remote', 'add', 'origin', 'https://github.com/acme/repo.git', cwd=root)
    git_repo['git']('remote', 'add', 'upstream', 'https://github.com/upstream/repo.git', cwd=root)
    branch = f'feat/fork-{new_id("b")[:8]}'
    worktree = root.parent / f'wt-{branch.split("/")[-1]}'
    git_repo['git']('worktree', 'add', '-b', branch, str(worktree), 'main')
    git_repo['git']('config', f'branch.{branch}.remote', 'origin', cwd=worktree)
    git_repo['git']('config', f'branch.{branch}.merge', 'refs/heads/main', cwd=worktree)

    data = client.post('/api/discovery/preview', json={'path': str(worktree)}).json()
    assert data['publishRemote'] == 'origin'
    assert data['prBase'] == 'develop'
    assert data['baseBranch'] != data['prBase']
    assert data['existingPr']['number'] == 42
    assert data['sources']['prBase'] == 'github'


def test_preferencia_salva_tem_prioridade(client: TestClient, git_repo) -> None:
    _, _, worktree = make_repo(git_repo)
    opened = client.post('/api/discovery/open', json={'path': str(worktree)}).json()
    saved = client.put('/api/discovery/preferences', json={
        'projectId': opened['projectId'], 'baseBranch': 'master',
        'publishRemote': 'origin', 'prRepository': 'acme/other', 'prBase': 'release',
    }).json()
    assert saved['baseBranch'] == 'master'

    data = client.post('/api/discovery/preview', json={'path': str(worktree)}).json()
    assert data['baseBranch'] == 'master'
    assert data['sources']['baseBranch'] == 'salvo'
    assert data['prBase'] == 'release'


def test_github_indisponivel_usa_dados_locais(client: TestClient, git_repo, monkeypatch) -> None:
    monkeypatch.setattr(github_module, 'get_client', lambda: FakeGitHub(authenticated=False))
    _, _, worktree = make_repo(git_repo)
    data = client.post('/api/discovery/preview', json={'path': str(worktree)}).json()
    assert data['branch']
    assert data['prBase'] in ('main', 'master')
    assert data['tools']['gitHub']['authenticated'] is False
    # Sem remoto configurado, a base fica incerta e a escolha é sinalizada (a fila ainda pode ser preparada).
    assert any(item['key'] == 'baseBranch' for item in data['ambiguities'])


def test_branch_base_nao_fica_pronta(client: TestClient, git_repo) -> None:
    root = git_repo['root']
    data = client.post('/api/discovery/preview', json={'path': str(root)}).json()
    assert data['branch'] == 'main'
    assert data['ready'] is False


def test_um_unico_remoto_nao_gera_ambiguidade(client: TestClient, git_repo) -> None:
    """`git remote -v` repete o nome para fetch/push; não pode virar dois remotos."""
    root = git_repo['root']
    git_repo['git']('remote', 'add', 'origin', 'https://github.com/acme/repo.git')
    data = client.post('/api/discovery/preview', json={'path': str(root)}).json()
    assert [item['name'] for item in data['remotes']] == ['origin']
    assert not any(item['key'] == 'publishRemote' for item in data['ambiguities'])
    assert data['publishRemote'] == 'origin'


def test_caminho_local_bloqueado_no_remoto(client: TestClient, git_repo, monkeypatch) -> None:
    from dataclasses import replace

    from app.config import settings
    from app.remote import auth

    monkeypatch.setattr(auth, 'settings', replace(settings, remote_password='senha'))
    set_remote_active(True)
    login = client.post('/api/remote/login', json={'password': 'senha'})
    csrf = login.json()['csrf']
    response = client.post(
        '/api/discovery/preview', json={'path': str(git_repo['root'])},
        headers={'x-csrf-token': csrf},
    )
    assert response.status_code == 403
    assert response.json()['code'] == 'LOCAL_ONLY'
