import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.domain.utils import new_id, utc_now
from app.opencode.client import OpenCodeClient
from app.queue import engine as engine_module
from app.queue import persistence as store
from app.queue.engine import engine
from conftest import make_git_project


EVENTS: list[str] = []
DELAY = {'seconds': 0.05}


class FakeClient(OpenCodeClient):
    """Cliente determinístico para o motor: confirma conclusão com evento estruturado."""

    async def run(self, prompt, cwd, *, session_id='', model='', agent='', on_line=None,
                  timeout=None, process_holder=None):
        from app.opencode.client import RunResult

        EVENTS.append(f"start:{prompt}")
        if on_line:
            await on_line('out {"type":"text","text":"inicio"}\n')
        await asyncio.sleep(DELAY['seconds'])
        attempts_of_prompt = sum(1 for event in EVENTS if event == f'start:{prompt}')
        if 'FALHA' in prompt and attempts_of_prompt == 1:
            EVENTS.append(f"end:{prompt}")
            return RunResult(status='failure', error='falha simulada', exit_code=1,
                             events=[{'type': 'error', 'error': 'falha simulada'}])
        if 'ERRO_SAIDA' in prompt:
            EVENTS.append(f"end:{prompt}")
            return RunResult(status='failure', error='codigo zero com erro na saida', exit_code=0,
                             events=[{'type': 'error', 'error': 'erro na saida'}])
        EVENTS.append(f"end:{prompt}")
        return RunResult(status='success', session_id='sim-1', exit_code=0,
                         events=[{'type': 'result', 'status': 'success', 'sessionID': 'sim-1'}])


@pytest.fixture(autouse=True)
def reset_events(monkeypatch):
    EVENTS.clear()
    monkeypatch.setattr(engine_module, 'OpenCodeClient', FakeClient)


def make_batch(client: TestClient, prompts: list[str]):
    project_id, workspace_id = make_git_project(client, __import__('pathlib').Path(
        os.environ['OCILIMIT_TEST_REPO']
    ))
    branch = f"feat/q-{int(time.time() * 1000) % 1_000_000}"
    created = client.post(
        f'/api/git/workspaces/{workspace_id}/branches',
        json={'branch': branch, 'startRef': 'refs/heads/main'},
    )
    assert created.status_code == 200, created.text
    batch = client.post('/api/batches', params={'workspaceId': workspace_id}, json={'name': 'Fila'}).json()
    client.post(
        f"/api/batches/{batch['id']}/items",
        params={'workspaceId': workspace_id},
        json=[{'title': f'Item {i}', 'content': text} for i, text in enumerate(prompts, 1)],
    )
    return workspace_id, batch['id']


@pytest.fixture
def repo_env(git_repo, monkeypatch):
    monkeypatch.setenv('OCILIMIT_TEST_REPO', str(git_repo['root']))
    return git_repo


def wait_status(client: TestClient, batch_id: str, statuses: set[str], timeout=12) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f'/api/queue/batches/{batch_id}').json()
        if state['status'] in statuses:
            return state
        time.sleep(0.05)
    raise AssertionError(f"status {state['status']} not in {statuses}")


def test_executa_tres_prompts_em_sequencia(client: TestClient, repo_env) -> None:
    workspace_id, batch_id = make_batch(client, ['um', 'dois', 'três'])
    state = client.post(f'/api/queue/batches/{batch_id}/start').json()
    assert state['status'] == 'running'

    final = wait_status(client, batch_id, {'completed'})
    assert [a['status'] for a in final['attempts']] == ['success'] * 3
    starts = [event for event in EVENTS if event.startswith('start:')]
    assert starts == ['start:um', 'start:dois', 'start:três']
    for index in range(2):
        assert EVENTS.index(f'end:{["um", "dois", "três"][index]}') < EVENTS.index(starts[index + 1])


def test_falha_mantem_terceiro_pendente_e_retry_cria_nova_tentativa(client: TestClient, repo_env) -> None:
    workspace_id, batch_id = make_batch(client, ['ok', 'FALHA etapa', 'terceiro'])
    client.post(f'/api/queue/batches/{batch_id}/start')
    failed = wait_status(client, batch_id, {'failed'})
    assert failed['items'][0]['status'] == 'done'
    assert failed['items'][1]['status'] == 'failed'
    assert failed['items'][2]['status'] == 'pending'
    assert len(failed['attempts']) == 2

    retry_target = next(a for a in failed['attempts'] if a['status'] == 'failure')
    retried = client.post(
        f"/api/queue/attempts/{retry_target['id']}/retry", json={'continueSession': False}
    )
    assert retried.status_code == 200, retried.text
    final = wait_status(client, batch_id, {'completed'})
    assert len(final['attempts']) == 4  # ok + falha + repetição + terceiro
    repeated = [a for a in final['attempts'] if a['resumeOf'] == retry_target['id']]
    assert len(repeated) == 1
    assert repeated[0]['promptSnapshot'] == 'FALHA etapa'


def test_segunda_aba_nao_inicia_duplicado(client: TestClient, repo_env) -> None:
    _, batch_id = make_batch(client, ['lento'])
    DELAY['seconds'] = 0.8
    try:
        first = client.post(f'/api/queue/batches/{batch_id}/start')
        assert first.status_code == 200
        second = client.post(f'/api/queue/batches/{batch_id}/start')
        assert second.status_code == 409
        assert second.json()['code'] == 'ALREADY_RUNNING'
        wait_status(client, batch_id, {'completed'})
    finally:
        DELAY['seconds'] = 0.05


def test_pause_termina_etapa_e_sobrevive_a_reinicio(client: TestClient, repo_env) -> None:
    _, batch_id = make_batch(client, ['a', 'b'])
    client.post(f'/api/queue/batches/{batch_id}/start')
    paused_requested = client.post(f'/api/queue/batches/{batch_id}/pause').json()
    assert paused_requested['status'] == 'pausing'
    assert paused_requested['pauseRequested'] is True
    final = wait_status(client, batch_id, {'paused'})
    assert final['pauseRequested'] is False
    assert final['status'] == 'paused'

    with TestClient(client.app) as restarted:
        state = restarted.get(f'/api/queue/batches/{batch_id}').json()
    assert state['status'] == 'paused'


def test_cancel_registra_tentativa(client: TestClient, repo_env) -> None:
    _, batch_id = make_batch(client, ['cancelar'])
    client.post(f'/api/queue/batches/{batch_id}/start')
    result = client.post(f'/api/queue/batches/{batch_id}/cancel').json()
    assert result['status'] == 'cancelled'
    assert result['attempts'][0]['status'] in {'running', 'cancelled'}


def test_recuperacao_sem_repeticao_automatica(client: TestClient, repo_env) -> None:
    workspace_id, batch_id = make_batch(client, ['pendente'])
    item_id = client.get(f'/api/queue/batches/{batch_id}').json()['items'][0]['id']
    _connect = __import__('app.db.connection', fromlist=['connect']).connect
    conn = _connect()
    try:
        attempt_id = new_id('attempt')
        conn.execute(
            'INSERT INTO attempts (id, batch_id, item_id, workspace_id, prompt_snapshot, created_at, status) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (attempt_id, batch_id, item_id, workspace_id, 'pendente', utc_now(), 'running'),
        )
        conn.execute("UPDATE batches SET status = 'running' WHERE id = ?", (batch_id,))
        conn.commit()
    finally:
        conn.close()
    recovered = client.post('/api/queue/recover').json()
    assert attempt_id in recovered['interrupted']
    attempts = client.get(f'/api/workspaces/{workspace_id}/attempts').json()
    assert attempts[0]['status'] == 'interrupted'


def test_prompt_longo_e_rejeitado_sem_truncar() -> None:
    with pytest.raises(Exception) as exc:
        OpenCodeClient.validate_prompt('x' * 40_000)
    assert 'excede' in str(exc.value)


def test_erro_com_codigo_zero_bloqueia(client: TestClient, repo_env) -> None:
    _, batch_id = make_batch(client, ['ERRO_SAIDA'])
    client.post(f'/api/queue/batches/{batch_id}/start')
    final = wait_status(client, batch_id, {'failed'})
    assert final['attempts'][0]['exitCode'] == 0
    assert final['attempts'][0]['status'] == 'failure'


def test_simulador_real_transporta_texto(client: TestClient, fake_opencode, git_repo, monkeypatch) -> None:
    os.environ['SIM_LOG'] = str(fake_opencode['log'])
    os.environ['SIM_DELAY'] = '0'
    client.put('/api/queue/opencode/config', json={'executable': fake_opencode['path']})
    result = client.post('/api/queue/opencode/test')
    assert result.status_code == 200
    assert result.json()['exitCode'] == 0
    assert 'ILIMIT' in fake_opencode['log'].read_text(encoding='utf-8')
