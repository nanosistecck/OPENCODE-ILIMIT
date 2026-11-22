from fastapi.testclient import TestClient

from conftest import make_project_and_workspaces


def test_mensagem_persiste_e_fica_isolada_por_espaco(client: TestClient) -> None:
    _, first, second = make_project_and_workspaces(client)

    state_first = client.get(f"/api/workspaces/{first}/state").json()
    conversation_id = state_first["conversation"]["id"]
    assert state_first["workspace"]["branch"] == "feat/canvas"
    assert state_first["workspace"]["workDir"] == "C:/work/nia-canvas"

    sent = client.post(
        f"/api/workspaces/{first}/messages",
        params={"conversationId": conversation_id},
        json={"content": "Mensagem somente da branch canvas"},
    )
    assert sent.status_code == 201
    assert sent.json()["status"] == "sent"

    reloaded = client.get(f"/api/workspaces/{first}/state").json()
    assert reloaded["conversation"]["messages"][0]["content"] == "Mensagem somente da branch canvas"

    other = client.get(f"/api/workspaces/{second}/state").json()
    assert other["conversation"]["messages"] == []
    assert other["workspace"]["branch"] == "feat/apis"

    crossed = client.post(
        f"/api/workspaces/{second}/messages",
        params={"conversationId": conversation_id},
        json={"content": "Tentativa de vínculo cruzado"},
    )
    assert crossed.status_code == 404
    assert crossed.json()["code"] == "NOT_FOUND"


def test_dados_sobrevivem_a_novo_client_simulando_reinicio(client: TestClient) -> None:
    _, first, _ = make_project_and_workspaces(client)
    conversation_id = client.get(f"/api/workspaces/{first}/state").json()["conversation"]["id"]
    client.post(
        f"/api/workspaces/{first}/messages",
        params={"conversationId": conversation_id},
        json={"content": "Persistida após reinício"},
    )

    with TestClient(client.app) as restarted:
        state = restarted.get(f"/api/workspaces/{first}/state").json()
    assert state["conversation"]["messages"][0]["content"] == "Persistida após reinício"


def test_projeto_aceita_base_diferente_e_edicao(client: TestClient) -> None:
    project = client.post(
        "/api/projects",
        json={"name": "Legado", "baseBranch": "develop", "objective": "Projeto existente"},
    ).json()
    assert project["baseBranch"] == "develop"

    workspace = client.post(
        f"/api/projects/{project['id']}/workspaces",
        json={"name": "Trabalho", "branch": "feat/legado", "baseBranch": "release/1.0"},
    ).json()
    assert workspace["base"] == "release/1.0"

    updated = client.patch(
        f"/api/workspaces/{workspace['id']}",
        json={"workDir": "D:/repos/legado"},
    ).json()
    assert updated["workDir"] == "D:/repos/legado"
