from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.git import service
from conftest import make_git_project, make_project_and_workspaces


def test_probe_resolve_subpasta_e_overview(client: TestClient, git_repo) -> None:
    subfolder = git_repo["root"] / "subpasta"
    subfolder.mkdir()
    probe = client.post("/api/git/probe", json={"path": str(subfolder)})
    assert probe.status_code == 200
    data = probe.json()
    assert Path(data["root"]).resolve() == git_repo["root"].resolve()
    assert data["state"]["branch"] == "main"
    assert data["state"]["hasCommits"] is True

    project_id, _ = make_git_project(client, git_repo["root"])
    overview = client.get(f"/api/git/projects/{project_id}/overview").json()
    names = {item["name"] for item in overview["refs"]["local"]}
    remotes = {item["name"] for item in overview["refs"]["remote"]}
    assert "main" in names
    assert "origin/main" in remotes
    assert overview["refs"]["suggestions"][0]["name"] == "main"


def test_criar_duas_worktrees_preserva_original(client: TestClient, git_repo) -> None:
    project_id, first = make_git_project(client, git_repo["root"])
    second = client.post(
        f"/api/projects/{project_id}/workspaces",
        json={"name": "Segundo", "branch": "feat/segundo"},
    ).json()["id"]

    before_head = git_repo["git"]("rev-parse", "HEAD")
    before_branch = git_repo["git"]("rev-parse", "--abbrev-ref", "HEAD")

    a = client.post(
        f"/api/git/workspaces/{first}/branches",
        json={"branch": "feat/primeira", "startRef": "refs/heads/main"},
    )
    b = client.post(
        f"/api/git/workspaces/{second}/branches",
        json={"branch": "feat/segunda", "startRef": "refs/remotes/origin/main"},
    )
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    assert a.json()["path"] != b.json()["path"]

    for workspace_id, branch in ((first, "feat/primeira"), (second, "feat/segunda")):
        state = client.get(f"/api/workspaces/{workspace_id}/state").json()
        assert state["git"]["gitStatus"] == "ready"
        assert state["git"]["linked"] is True
        assert state["git"]["simulated"] is False
        assert state["git"]["branch"] == branch
        assert state["git"]["verification"]["ready"] is True

    assert git_repo["git"]("rev-parse", "HEAD") == before_head
    assert git_repo["git"]("rev-parse", "--abbrev-ref", "HEAD") == before_branch


def test_status_e_diff_isolados_com_espacos_e_acentos(client: TestClient, git_repo) -> None:
    project_id, first = make_git_project(client, git_repo["root"])
    second = client.post(
        f"/api/projects/{project_id}/workspaces",
        json={"name": "Outro", "branch": "feat/outro"},
    ).json()["id"]
    first_path = client.post(
        f"/api/git/workspaces/{first}/branches",
        json={"branch": "feat/status", "startRef": "refs/heads/main"},
    ).json()["path"]
    client.post(
        f"/api/git/workspaces/{second}/branches",
        json={"branch": "feat/limpo", "startRef": "refs/heads/main"},
    )

    changed = Path(first_path) / "noticias prioritárias.md"
    changed.write_text("# Notícias\n\nAcentuação: çãõ.\n", encoding="utf-8")
    staged = Path(first_path) / "rascunho.txt"
    staged.write_text("linha preparada\n", encoding="utf-8")
    git_repo["git"]("add", "rascunho.txt", cwd=first_path)

    status = client.get(f"/api/git/workspaces/{first}/status").json()
    paths = {item["path"] for item in status["files"]}
    assert "noticias prioritárias.md" in paths
    assert "rascunho.txt" in paths
    assert status["summary"]["staged"] == 1
    assert status["summary"]["unstaged"] == 1

    diff = client.get(
        f"/api/git/workspaces/{first}/diff",
        params={"file": "noticias prioritárias.md", "untracked": True},
    ).json()
    assert "Acentuação: çãõ" in diff["text"]

    other = client.get(f"/api/git/workspaces/{second}/status").json()
    assert other["summary"]["total"] == 0


def test_diff_rejeita_caminho_fora_da_pasta(client: TestClient, git_repo) -> None:
    _, workspace_id = make_git_project(client, git_repo["root"])
    client.post(
        f"/api/git/workspaces/{workspace_id}/branches",
        json={"branch": "feat/seguro", "startRef": "refs/heads/main"},
    )
    response = client.get(
        f"/api/git/workspaces/{workspace_id}/diff",
        params={"file": "../README.md"},
    )
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "fora da pasta" in response.json()["reason"]


def test_vincular_worktree_existente_e_reinicio(client: TestClient, git_repo) -> None:
    project = client.post("/api/projects", json={"name": "Git", "baseBranch": "main"}).json()
    workspace_id = client.post(
        f"/api/projects/{project['id']}/workspaces",
        json={"name": "Existente", "branch": "feat/existente"},
    ).json()["id"]
    client.post(
        f"/api/git/projects/{project['id']}/repository", json={"path": str(git_repo["root"])}
    )
    target = settings.worktrees_dir / "feat-existente"
    git_repo["git"]("worktree", "add", "-b", "feat/existente", str(target), "main")

    linked = client.post(
        f"/api/git/workspaces/{workspace_id}/open",
        json={"action": "link", "path": str(target)},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["path"] == str(target.resolve())
    assert linked.json()["branch"] == "feat/existente"

    with TestClient(client.app) as restarted:
        state = restarted.get(f"/api/workspaces/{workspace_id}/state").json()
    assert state["git"]["gitStatus"] == "ready"
    assert state["git"]["workDir"] == str(target.resolve())


def test_verificacao_motivos_especificos(client: TestClient, git_repo) -> None:
    _, workspace_id = make_git_project(client, git_repo["root"])
    path = client.post(
        f"/api/git/workspaces/{workspace_id}/branches",
        json={"branch": "feat/verificar", "startRef": "refs/heads/main"},
    ).json()["path"]

    ok = client.post(f"/api/git/workspaces/{workspace_id}/verify").json()
    assert ok["ready"] is True

    git_repo["git"]("checkout", "-b", "outra-branch", cwd=path)
    changed = client.post(f"/api/git/workspaces/{workspace_id}/verify").json()
    assert "BRANCH_CHANGED" in changed["reasons"]
    assert changed["ready"] is False

    git_repo["git"]("checkout", "--detach", cwd=path)
    detached = client.post(f"/api/git/workspaces/{workspace_id}/verify").json()
    assert "DETACHED_HEAD" in detached["reasons"]


def test_recuperacao_apos_falha_do_sqlite(client: TestClient, git_repo, monkeypatch) -> None:
    _, workspace_id = make_git_project(client, git_repo["root"])
    original = service._persist_binding

    class FailingConnection:
        """Delega a transação, mas falha somente no UPDATE do vínculo."""

        def __init__(self, real):
            self._real = real

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *args):
            return self._real.__exit__(*args)

        def execute(self, sql, *args):
            if "UPDATE workspaces SET git_status" in sql:
                raise RuntimeError("sqlite indisponível")
            return self._real.execute(sql, *args)

    def wrapped(conn, *args, **kwargs):
        return original(FailingConnection(conn), *args, **kwargs)

    monkeypatch.setattr(service, "_persist_binding", wrapped)
    failed = client.post(
        f"/api/git/workspaces/{workspace_id}/branches",
        json={"branch": "feat/recuperar", "startRef": "refs/heads/main"},
    )
    assert failed.status_code == 409
    assert failed.json()["code"] == "WORKTREE_CREATED_DB_FAILED"
    worktree_path = failed.json()["detail"]["path"]
    assert Path(worktree_path).exists()

    monkeypatch.setattr(service, "_persist_binding", original)
    recovered = client.post(
        f"/api/git/workspaces/{workspace_id}/open",
        json={"action": "link", "path": worktree_path, "branch": "feat/recuperar"},
    )
    assert recovered.status_code == 200, recovered.text
    worktrees = git_repo["git"]("worktree", "list", "--porcelain")
    assert worktrees.count("branch refs/heads/feat/recuperar") == 1


def test_espacos_antigos_ficam_pendentes_e_dados_preservados(client: TestClient) -> None:
    _, first, second = make_project_and_workspaces(client)
    conversation_id = client.get(f"/api/workspaces/{first}/state").json()["conversation"]["id"]
    client.post(
        f"/api/workspaces/{first}/messages",
        params={"conversationId": conversation_id},
        json={"content": "mensagem antiga"},
    )
    for workspace_id in (first, second):
        git_info = client.get(f"/api/workspaces/{workspace_id}/git").json()
        assert git_info["gitStatus"] == "pending"
        assert git_info["linked"] is False
    assert client.get(f"/api/workspaces/{first}/state").json()["conversation"]["messages"]
