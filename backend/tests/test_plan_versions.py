from fastapi.testclient import TestClient

from conftest import make_project_and_workspaces


def _plan(prompt_two: str) -> dict:
    return {
        "objective": "Entregar canvas infinito",
        "steps": [
            {
                "id": "s1", "order": 1, "title": "Câmera", "description": "Modelo",
                "dependencies": [], "acceptanceCriteria": "zoom limitado",
                "prompt": "Implementar câmera",
            },
            {
                "id": "s2", "order": 2, "title": "Gestos", "description": "Pan/zoom",
                "dependencies": ["s1"], "acceptanceCriteria": "touch em 360px",
                "prompt": prompt_two,
            },
            {
                "id": "s3", "order": 3, "title": "Persistência", "description": "Salvar",
                "dependencies": ["s2"], "acceptanceCriteria": "restaurar viewport",
                "prompt": "Persistir câmera",
            },
        ],
    }


def test_nova_versao_preserva_lote_antigo(client: TestClient) -> None:
    _, workspace_id, _ = make_project_and_workspaces(client)

    first = client.put(f"/api/plans/{workspace_id}", json=_plan("Prompt original da etapa 2"))
    assert first.status_code == 200
    assert first.json()["version"] == 1
    first_version_id = first.json()["versions"][0]["id"]

    queue = client.post(f"/api/workspaces/{workspace_id}/queue")
    assert queue.status_code == 201
    batch = queue.json()
    assert batch["sourceVersionId"] == first_version_id
    assert [item["title"] for item in batch["items"]] == ["Câmera", "Gestos", "Persistência"]
    assert batch["items"][1]["content"] == "Prompt original da etapa 2"

    second = client.put(f"/api/plans/{workspace_id}", json=_plan("Prompt revisado da etapa 2"))
    assert second.status_code == 200
    assert second.json()["version"] == 2

    old_batch = client.get(
        f"/api/batches/{batch['id']}", params={"workspaceId": workspace_id}
    ).json()
    assert old_batch["sourceVersionId"] == first_version_id
    assert old_batch["items"][1]["content"] == "Prompt original da etapa 2"


def test_dependencias_invalidas_sao_rejeitadas(client: TestClient) -> None:
    _, workspace_id, _ = make_project_and_workspaces(client)
    assert client.put(f"/api/plans/{workspace_id}", json=_plan("ok")).status_code == 200

    cycle = _plan("x")
    cycle["steps"][0]["dependencies"] = ["s2"]
    response = client.put(f"/api/plans/{workspace_id}", json=cycle)
    assert response.status_code == 422
    assert response.json()["code"] in {"CYCLE", "ORDER_VIOLATION"}
    assert client.get(f"/api/plans/{workspace_id}").json()["version"] == 1

    out_of_order = _plan("y")
    out_of_order["steps"][0]["dependencies"] = ["s3"]
    response = client.put(f"/api/plans/{workspace_id}", json=out_of_order)
    assert response.status_code == 422
    assert response.json()["code"] in {"FOREIGN_DEPENDENCY", "ORDER_VIOLATION"}

    foreign = _plan("z")
    foreign["steps"][0]["dependencies"] = ["inexistente"]
    response = client.put(f"/api/plans/{workspace_id}", json=foreign)
    assert response.status_code == 422
    assert response.json()["code"] == "FOREIGN_DEPENDENCY"


def test_fila_pode_ser_gerada_de_versao_escolhida(client: TestClient) -> None:
    _, workspace_id, _ = make_project_and_workspaces(client)
    v1 = client.put(f"/api/plans/{workspace_id}", json=_plan("antigo")).json()
    old_version_id = v1["versions"][0]["id"]
    client.put(f"/api/plans/{workspace_id}", json=_plan("novo"))

    batch = client.post(
        f"/api/workspaces/{workspace_id}/queue", params={"versionId": old_version_id}
    ).json()
    assert batch["sourceVersionId"] == old_version_id
    assert batch["items"][1]["content"] == "antigo"
