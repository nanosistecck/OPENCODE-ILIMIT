from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import connect
from app.remote import auth, events
from app.remote.state import set_remote_active
from conftest import make_git_project

PASSWORD = 'senha-de-teste'


@pytest.fixture(autouse=True)
def remote_reset(monkeypatch):
    set_remote_active(False)
    monkeypatch.setattr(auth, 'settings', replace(settings, remote_password=PASSWORD))
    yield
    set_remote_active(False)


def test_remote_desativado_por_padrao(client: TestClient) -> None:
    status = client.get('/api/remote/status').json()
    assert status['active'] is False
    assert client.get('/api/projects').status_code == 200


def test_login_cookie_csrf_e_logout(client: TestClient) -> None:
    set_remote_active(True)
    login = client.post('/api/remote/login', json={'password': PASSWORD})
    assert login.status_code == 200, login.text
    csrf = login.json()['csrf']
    assert csrf

    assert client.get('/api/projects').status_code == 200
    sem_csrf = client.post('/api/projects', json={'name': 'sem csrf'})
    assert sem_csrf.status_code == 403
    assert sem_csrf.json()['code'] == 'CSRF_INVALID'

    com_csrf = client.post(
        '/api/projects', json={'name': 'com csrf'}, headers={'x-csrf-token': csrf}
    )
    assert com_csrf.status_code in (200, 201), com_csrf.text

    assert client.post('/api/remote/logout', headers={'x-csrf-token': csrf}).status_code == 200
    assert client.get('/api/projects').status_code == 401


def test_sessao_expirada_ou_revogada_nao_acessa(client: TestClient) -> None:
    set_remote_active(True)
    login = client.post('/api/remote/login', json={'password': PASSWORD})
    csrf = login.json()['csrf']
    client.post('/api/remote/logout', headers={'x-csrf-token': csrf})
    assert client.get('/api/projects').status_code == 401


def test_eventos_sequencia_e_isolamento(client: TestClient) -> None:
    conn = connect()
    try:
        first = events.publish(conn, 'ws-a', 'queue.state.changed', {'step': 1}, 'iniciou')
        second = events.publish(conn, 'ws-a', 'chat.message.created', {'step': 2}, 'respondeu')
        other = events.publish(conn, 'ws-b', 'queue.state.changed', {}, 'outro espaço')
        assert second == first + 1
        payload = client.get('/api/events', params={'workspaceId': 'ws-a', 'after': first}).json()
        assert [item['sequence'] for item in payload['events']] == [second]
        assert other not in [item['sequence'] for item in payload['events']]
        assert payload['sequence'] >= second
    finally:
        conn.close()


def test_idempotencia_de_escrita(client: TestClient, git_repo) -> None:
    _, workspace_id = make_git_project(client, git_repo['root'])
    headers = {'idempotency-key': 'criar-lote-unico-1'}
    first = client.post(
        '/api/batches', params={'workspaceId': workspace_id}, json={'name': 'Lote'},
        headers=headers,
    )
    assert first.status_code in (200, 201), first.text
    second = client.post(
        '/api/batches', params={'workspaceId': workspace_id}, json={'name': 'Lote'},
        headers=headers,
    )
    assert second.status_code in (200, 201)
    assert second.headers.get('x-idempotent-replay') == '1'
    assert second.json()['id'] == first.json()['id']
    batches = client.get(f'/api/workspaces/{workspace_id}/batches').json()
    assert len(batches) == 1


def test_websocket_envia_snapshot_e_evento(client: TestClient) -> None:
    with client.websocket_connect('/ws/events?workspaceId=ws-ws') as socket:
        snapshot = socket.receive_json()
        assert snapshot['type'] == 'snapshot'
        assert snapshot['workspaceId'] == 'ws-ws'
        conn = connect()
        try:
            events.publish(conn, 'ws-ws', 'queue.state.changed', {'step': 3}, 'pausa confirmada')
        finally:
            conn.close()
        event = socket.receive_json()
        assert event['type'] == 'queue.state.changed'
        assert event['context']['step'] == 3
        assert event['sequence'] > snapshot['sequence'] - 1
