import json

import pytest
from fastapi.testclient import TestClient

from app.assistant import service as assistant_service
from app.domain.utils import new_id
from app.opencode.client import OpenCodeClient, RunResult
from conftest import make_git_project

MODE = {'proposal': 'valid', 'analysis': 'valid'}


class AssistantFake(OpenCodeClient):
    async def run(self, prompt, cwd, *, session_id='', model='', agent='', on_line=None,
                  timeout=None, process_holder=None):
        if on_line:
            await on_line('out {"type":"text","text":"processando"}\n')
        if 'Analise este espaço' in prompt:
            text = json.dumps({
                'features': ['já existe leitura do contrato'],
                'gaps': ['falta revisão automatizada'],
                'evidence': ['backend/app/domain/plans.py'],
                'assumptions': ['projeto existente'],
                'questions': ['Qual critério de aceite priorizar?'],
            }) if MODE['analysis'] == 'valid' else 'análise sem JSON'
        elif 'plano estruturado' in prompt:
            if MODE['proposal'] == 'invalid':
                text = '{"objective": "incompleto"}'
            elif MODE['proposal'] == 'cycle':
                text = json.dumps({
                    'objective': 'Plano com ciclo', 'scope': 'teste', 'decisions': [],
                    'questions': [], 'steps': [
                        {'title': 'A', 'objective': '', 'dependencies': [2],
                         'prompt': 'fazer A', 'acceptanceCriteria': 'A pronto'},
                        {'title': 'B', 'objective': '', 'dependencies': [1],
                         'prompt': 'fazer B', 'acceptanceCriteria': 'B pronto'},
                    ],
                })
            else:
                text = json.dumps({
                    'objective': 'Entregar revisão', 'scope': 'escopo do espaço',
                    'decisions': [{'text': 'manter CLI', 'needsAnswer': False}],
                    'questions': ['Qual critério priorizar?'],
                    'steps': [
                        {'title': 'Câmera', 'objective': 'base', 'dependencies': [],
                         'prompt': 'Implementar câmera', 'acceptanceCriteria': 'zoom limitado'},
                        {'title': 'Revisão', 'objective': 'validar', 'dependencies': [1],
                         'prompt': 'Revisar câmera', 'acceptanceCriteria': 'revisão registrada'},
                    ],
                })
        else:
            text = 'Resposta do chat para ' + prompt[-40:]
        return RunResult(status='success', session_id=session_id or 'ses-chat-' + new_id('s'),
                         exit_code=0, final_text=text,
                         events=[{'type': 'result', 'status': 'success'}])


@pytest.fixture(autouse=True)
def use_fake(monkeypatch):
    MODE['proposal'] = 'valid'
    MODE['analysis'] = 'valid'
    monkeypatch.setattr(assistant_service, '_client', lambda conn: AssistantFake(''))


def make_workspace(client: TestClient, git_repo):
    project_id, workspace_id = make_git_project(client, git_repo['root'])
    created = client.post(
        f'/api/git/workspaces/{workspace_id}/branches',
        json={'branch': f"feat/assistant-{new_id('b')[:8]}", 'startRef': 'refs/heads/main'},
    )
    assert created.status_code == 200, created.text
    return project_id, workspace_id


def publish(client: TestClient, workspace_id: str, answers: str = ''):
    analysis = client.post(f'/api/assistant/analyze/{workspace_id}', json={'objective': 'teste'}).json()
    proposal = client.post(
        f'/api/assistant/plan/{workspace_id}/proposal',
        json={'analysisId': analysis['id'], 'answers': answers},
    ).json()
    return analysis, proposal


def test_chat_isolado_por_espaco(client: TestClient, git_repo) -> None:
    _, first = make_workspace(client, git_repo)
    _, second = make_workspace(client, git_repo)
    a = client.post(f'/api/assistant/chat/{first}/messages', json={'content': 'mensagem A'}).json()
    b = client.post(f'/api/assistant/chat/{second}/messages', json={'content': 'mensagem B'}).json()
    first_messages = a['conversations'][0]['messages']
    second_messages = b['conversations'][0]['messages']
    assert any('mensagem A' in item['content'] for item in first_messages)
    assert not any('mensagem A' in item['content'] for item in second_messages)
    assert a['conversations'][0]['sessionId'] != b['conversations'][0]['sessionId']
    assert client.get(f'/api/assistant/chat/{first}/state').json()['conversations'][0]['messages']


def test_analise_proposta_aprovacao_e_lote(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    analysis, proposal = publish(client, workspace_id)
    assert analysis['valid'] is True
    assert proposal['status'] == 'draft'
    assert [step['order'] for step in proposal['steps']] == [1, 2]
    assert proposal['steps'][1]['dependencies'] == ['step-1']

    plan = client.post(
        f'/api/assistant/plan/{workspace_id}/approve', json={'proposalId': proposal['id']}
    ).json()
    assert plan['version'] == 1
    assert plan['status'] == 'approved'

    batch = client.post(
        f'/api/assistant/plan/{workspace_id}/batch',
        json={'versionId': plan['versions'][0]['id']},
    ).json()
    assert [item['content'] for item in batch['items']] == ['Implementar câmera', 'Revisar câmera']
    again = client.post(
        f'/api/assistant/plan/{workspace_id}/batch',
        json={'versionId': plan['versions'][0]['id']},
    ).json()
    assert again['id'] == batch['id']
    forced = client.post(
        f'/api/assistant/plan/{workspace_id}/batch',
        json={'versionId': plan['versions'][0]['id'], 'force': True},
    ).json()
    assert forced['id'] != batch['id']


def test_proposta_invalida_nao_gera_lote(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    _, proposal = publish(client, workspace_id)
    MODE['proposal'] = 'invalid'
    _, invalid = publish(client, workspace_id)
    assert invalid['status'] == 'invalid'
    assert invalid['validationError']
    response = client.post(
        f'/api/assistant/plan/{workspace_id}/approve', json={'proposalId': invalid['id']}
    )
    assert response.status_code == 409


def test_dependencia_ciclica_e_rejeitada(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    MODE['proposal'] = 'cycle'
    _, proposal = publish(client, workspace_id)
    assert proposal['status'] == 'invalid'
    assert ('ciclo' in proposal['validationError'].lower()
            or 'depend' in proposal['validationError'].lower())


def test_nova_versao_preserva_lote(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    analysis, proposal = publish(client, workspace_id, answers='priorizar câmera')
    plan_v1 = client.post(
        f'/api/assistant/plan/{workspace_id}/approve', json={'proposalId': proposal['id']}
    ).json()
    version_id = plan_v1['versions'][0]['id']
    batch = client.post(
        f'/api/assistant/plan/{workspace_id}/batch', json={'versionId': version_id}
    ).json()
    _, proposal2 = publish(client, workspace_id, answers='resposta revisada')
    plan_v2 = client.post(
        f'/api/assistant/plan/{workspace_id}/approve', json={'proposalId': proposal2['id']}
    ).json()
    assert plan_v2['version'] == 2
    old = client.get(
        f"/api/batches/{batch['id']}", params={'workspaceId': workspace_id}
    ).json()
    assert old['sourceVersionId'] == version_id
    assert [item['content'] for item in old['items']] == ['Implementar câmera', 'Revisar câmera']


def test_nova_sessao_preserva_mensagens(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    state = client.post(f'/api/assistant/chat/{workspace_id}/messages', json={'content': 'original'}).json()
    original = state['conversations'][0]
    next_state = client.post(
        f'/api/assistant/chat/{workspace_id}/new-session',
        params={'conversationId': original['id']},
    ).json()
    assert any(item['id'] == original['id'] for item in next_state['conversations'])
    resumed = next(item for item in next_state['conversations'] if item['id'] != original['id'])
    assert resumed['sessionStatus'] == 'restarted'
    assert 'original' in resumed['summary']
    assert resumed['messages'][0]['kind'] == 'system'


def test_revisao_aponta_criterio_pendente(client: TestClient, git_repo) -> None:
    _, workspace_id = make_workspace(client, git_repo)
    batch = client.post('/api/batches', params={'workspaceId': workspace_id}, json={'name': 'Revisão'}).json()
    client.post(
        f"/api/batches/{batch['id']}/items",
        params={'workspaceId': workspace_id},
        json=[{'title': 'Feito', 'content': 'ok', 'acceptanceCriteria': 'critério feito'},
              {'title': 'Pendente', 'content': 'não executado', 'acceptanceCriteria': 'critério pendente'}],
    )
    _connect = __import__('app.db.connection', fromlist=['connect']).connect
    conn = _connect()
    try:
        conn.execute("UPDATE batch_items SET status = 'done' WHERE title = 'Feito'")
        conn.commit()
    finally:
        conn.close()
    review = client.post(
        f'/api/assistant/review/{workspace_id}', params={'batchId': batch['id']}
    ).json()
    statuses = {item['title']: item['status'] for item in review['criteria']}
    assert statuses['Pendente'] == 'pending'
    assert any(step['reason'] == 'pending' for step in review['suggestedSteps'])
    assert client.get(f'/api/assistant/review/{workspace_id}').json()['batchId'] == batch['id']
