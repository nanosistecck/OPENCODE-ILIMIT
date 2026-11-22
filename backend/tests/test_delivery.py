import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.delivery import gitops
from app.delivery import github as github_module
from app.domain.utils import new_id
from app.queue.engine import engine
from conftest import make_git_project

FAKE_STATE = {'prs': {}, 'uncertain': False}


class FakeGitHub:
    def detect(self):
        return {'found': True, 'path': 'fake-gh', 'version': 'gh test',
                'authenticated': True, 'host': 'github.com', 'error': ''}

    def find_open_pr(self, repository, source, target):
        for item in FAKE_STATE['prs'].values():
            if item.get('source') == source and item.get('target') == target:
                return {'number': item['number'], 'url': item['url'], 'state': 'open',
                        'isDraft': True, 'title': item['title']}
        return None

    def create_pr(self, repository, source, target, title, body, draft=True):
        if FAKE_STATE['uncertain']:
            return {'ok': False, 'error': 'timeout', 'uncertain': True}
        number = len(FAKE_STATE['prs']) + 1
        item = {'number': number, 'url': f'https://github.com/{repository}/pull/{number}',
                'source': source, 'target': target, 'title': title, 'body': body,
                'state': 'open', 'isDraft': draft}
        FAKE_STATE['prs'][number] = item
        return {'ok': True, 'url': item['url'], 'error': '', 'uncertain': False}

    def get_pr(self, repository, number):
        item = FAKE_STATE['prs'].get(int(number))
        if not item:
            return {'ok': False, 'error': 'not found'}
        return {'ok': True, **item, 'statusCheckRollup': []}


@pytest.fixture(autouse=True)
def fake_gh(monkeypatch):
    FAKE_STATE['prs'].clear()
    FAKE_STATE['uncertain'] = False
    monkeypatch.setattr(github_module, 'get_client', lambda: FakeGitHub())


def make_workspace(client: TestClient, git_repo):
    _, workspace_id = make_git_project(client, git_repo['root'])
    created = client.post(
        f'/api/git/workspaces/{workspace_id}/branches',
        json={'branch': f"feat/delivery-{new_id('b')[:8]}", 'startRef': 'refs/heads/main'},
    )
    assert created.status_code == 200, created.text
    return workspace_id, created.json()['path']


def make_preview(client, workspace_id, selected, message='Commit de teste'):
    response = client.post('/api/delivery/preview', json={
        'workspaceId': workspace_id, 'selectedPaths': selected, 'message': message,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_commit_apenas_arquivo_selecionado(client: TestClient, git_repo) -> None:
    workspace_id, worktree = make_workspace(client, git_repo)
    (Path(worktree) / 'primeiro.txt').write_text('primeiro\n', encoding='utf-8')
    (Path(worktree) / 'segundo.txt').write_text('segundo\n', encoding='utf-8')
    preview = make_preview(client, workspace_id, ['primeiro.txt'])

    result = client.post('/api/delivery/commit', json={
        'workspaceId': workspace_id, 'previewId': preview['previewId'],
        'selectedPaths': ['primeiro.txt'], 'message': 'Commit de teste',
    })
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['files'] == ['primeiro.txt']
    assert data['hash']
    state = client.get('/api/delivery/state', params={'workspaceId': workspace_id}).json()
    assert state['commits'][0]['hash'] == data['hash']
    with TestClient(client.app) as restarted:
        historical = restarted.get('/api/delivery/state', params={'workspaceId': workspace_id}).json()
    assert historical['commits'][0]['message'] == 'Commit de teste'


def test_preparado_fora_da_selecao_preserva_indice(client: TestClient, git_repo) -> None:
    workspace_id, worktree = make_workspace(client, git_repo)
    (Path(worktree) / 'fora.txt').write_text('fora\n', encoding='utf-8')
    git_repo['git']('add', 'fora.txt', cwd=worktree)
    (Path(worktree) / 'dentro.txt').write_text('dentro\n', encoding='utf-8')
    preview = make_preview(client, workspace_id, ['dentro.txt'])
    assert preview['stagedOutsideSelection'] == ['fora.txt']

    response = client.post('/api/delivery/commit', json={
        'workspaceId': workspace_id, 'previewId': preview['previewId'],
        'selectedPaths': ['dentro.txt'], 'message': 'x',
    })
    assert response.status_code == 409
    assert response.json()['code'] == 'STAGED_OUTSIDE_SELECTION'
    assert 'fora.txt' in gitops.staged_files(worktree)


def test_previa_desatualizada_exige_revisao(client: TestClient, git_repo) -> None:
    workspace_id, worktree = make_workspace(client, git_repo)
    (Path(worktree) / 'arquivo.txt').write_text('antes\n', encoding='utf-8')
    preview = make_preview(client, workspace_id, ['arquivo.txt'])
    (Path(worktree) / 'arquivo.txt').write_text('depois\n', encoding='utf-8')

    response = client.post('/api/delivery/commit', json={
        'workspaceId': workspace_id, 'previewId': preview['previewId'],
        'selectedPaths': ['arquivo.txt'], 'message': 'x',
    })
    assert response.status_code == 409
    assert response.json()['code'] == 'STALE_PREVIEW'
    assert response.json()['detail']['freshPreviewId']


def test_fila_bloqueia_escrita_mas_nao_consulta(client: TestClient, git_repo) -> None:
    workspace_id, _ = make_workspace(client, git_repo)
    class BusyTask:
        def done(self):
            return False

    task = BusyTask()
    engine._tasks['fake'] = task
    try:
        blocked = client.post('/api/delivery/preview', json={
            'workspaceId': workspace_id, 'selectedPaths': [], 'message': '',
        })
        assert blocked.status_code == 409
        assert blocked.json()['code'] == 'QUEUE_BUSY'
        state = client.get('/api/delivery/state', params={'workspaceId': workspace_id})
        assert state.status_code == 200
        assert state.json()['writable'] is False
    finally:
        engine._tasks.pop('fake', None)


def test_push_publica_e_configura_upstream(client: TestClient, git_repo, tmp_path) -> None:
    workspace_id, worktree = make_workspace(client, git_repo)
    bare = tmp_path / 'remote.git'
    git_repo['git']('init', '--bare', str(bare), cwd=tmp_path)
    git_repo['git']('remote', 'add', 'origin', str(bare), cwd=git_repo['root'])
    (Path(worktree) / 'publicado.txt').write_text('conteudo\n', encoding='utf-8')
    preview = make_preview(client, workspace_id, ['publicado.txt'])
    commit = client.post('/api/delivery/commit', json={
        'workspaceId': workspace_id, 'previewId': preview['previewId'],
        'selectedPaths': ['publicado.txt'], 'message': 'publicar',
    }).json()

    pushed = client.post('/api/delivery/push', json={
        'workspaceId': workspace_id, 'remote': 'origin', 'commitId': commit['id'],
    })
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()['upstream'].startswith('origin/')
    upstream = gitops.upstream(worktree, gitops_state_branch(client, workspace_id))
    assert upstream.startswith('origin/')


def gitops_state_branch(client: TestClient, workspace_id: str) -> str:
    return client.get('/api/delivery/state', params={'workspaceId': workspace_id}).json()['branch']


def test_pr_rascunho_base_diferente_e_existente(client: TestClient, git_repo) -> None:
    workspace_id, worktree = make_workspace(client, git_repo)
    conn_workspace = client.get(f'/api/workspaces/{workspace_id}').json()
    assert conn_workspace['base'] == 'main'
    preview = client.post('/api/delivery/pr/preview', json={
        'workspaceId': workspace_id, 'base': 'release/1.0',
    }).json()
    assert preview['target'] == 'release/1.0'
    assert 'Verificações registradas' in preview['body']
    assert 'Pendências conhecidas' in preview['body']

    created = client.post('/api/delivery/pr', json={
        'workspaceId': workspace_id, 'title': 'PR de teste', 'body': preview['body'],
        'base': 'release/1.0', 'draft': True,
    })
    assert created.status_code == 200, created.text
    assert created.json()['existing'] is False
    assert 'pull/1' in created.json()['pullRequest']['url']

    again = client.post('/api/delivery/pr', json={
        'workspaceId': workspace_id, 'title': 'outro', 'base': 'release/1.0',
    }).json()
    assert again['existing'] is True

    refreshed = client.post('/api/delivery/pr/refresh', json={'workspaceId': workspace_id})
    assert refreshed.status_code == 200
    assert refreshed.json()['ok'] is True


def test_pr_incerto_consultar_antes_de_repetir(client: TestClient, git_repo) -> None:
    workspace_id, _ = make_workspace(client, git_repo)
    client.post('/api/delivery/pr', json={'workspaceId': workspace_id, 'title': 'PR inicial'})
    FAKE_STATE['uncertain'] = True
    response = client.post('/api/delivery/pr', json={
        'workspaceId': workspace_id, 'forceNew': True,
    })
    assert response.status_code == 409
    assert response.json()['code'] == 'PR_UNCERTAIN'
    assert response.json()['detail']['existing'] is not None


def test_sanitizacao_de_credenciais() -> None:
    text = 'falha em https://user:supersecret@github.com/org/repo token=abc123'
    cleaned = gitops.sanitize(text)
    assert 'supersecret' not in cleaned
    assert 'abc123' not in cleaned
