"""Dados de teste em diretório temporário, fora das pastas do projeto."""

import os
import shutil
import subprocess
import tempfile

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="oc-ilimit-tests-")
os.environ["OCILIMIT_DATA_DIR"] = _TEST_DATA_DIR

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.connection import connect  # noqa: E402
from app.db.migrations import run_migrations  # noqa: E402
from app.main import app  # noqa: E402


def _reset_database() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = settings.db_path.with_name(settings.db_path.name + suffix)
        path.unlink(missing_ok=True)
    if settings.worktrees_dir.exists():
        shutil.rmtree(settings.worktrees_dir)
    settings.worktrees_dir.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        run_migrations(conn)
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def drain_engine():
    """Espera tarefas do motor terminarem antes de limpar o banco do próximo teste."""
    yield
    import time

    from app.queue.engine import engine

    deadline = time.time() + 6
    while time.time() < deadline and any(not task.done() for task in engine._tasks.values()):
        time.sleep(0.05)


@pytest.fixture
def client() -> TestClient:
    """Cada teste começa com um banco limpo; um novo client simula reinício."""
    _reset_database()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_opencode(tmp_path):
    """Executável de teste: emite JSON, aceita atraso e simula falha/erro na saída."""
    directory = tmp_path / "fake-opencode"
    directory.mkdir()
    log = directory / "prompts.log"
    script = directory / "fake.py"
    script.write_text(
        "import json, os, sys, time\n"
        "prompt = sys.argv[-1]\n"
        "with open(os.environ['SIM_LOG'], 'a', encoding='utf-8') as h:\n"
        "    h.write(prompt + '\\n---\\n')\n"
        "time.sleep(float(os.environ.get('SIM_DELAY', '0')))\n"
        "if 'FALHA' in prompt:\n"
        "    print(json.dumps({'type': 'error', 'error': 'falha simulada'}))\n"
        "    sys.exit(1)\n"
        "if 'ERRO_SAIDA' in prompt:\n"
        "    print(json.dumps({'type': 'error', 'error': 'erro informado na saida'}))\n"
        "    print(json.dumps({'type': 'result', 'status': 'success', 'sessionID': 'sim-1'}))\n"
        "else:\n"
        "    print(json.dumps({'type': 'text', 'text': 'ok'}))\n"
        "    print(json.dumps({'type': 'result', 'status': 'success', 'sessionID': 'sim-1'}))\n",
        encoding="utf-8",
    )
    wrapper = directory / "opencode.cmd"
    wrapper.write_text(f'@echo off\r\npython "{script}" %*\r\n', encoding="utf-8")
    return {"path": str(wrapper), "log": log}


@pytest.fixture
def git_repo(tmp_path):
    """Repositório descartável com commit inicial e ref remota local."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str, cwd=None) -> str:
        process = subprocess.run(
            ["git", *args], cwd=cwd or root, capture_output=True, text=True, check=True
        )
        return process.stdout.strip()

    git("init", "-b", "main")
    git("config", "user.email", "teste@example.com")
    git("config", "user.name", "Teste")
    (root / "README.md").write_text("# Repositorio de teste\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "commit inicial")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    return {"root": root, "git": git}


def make_git_project(test_client: TestClient, repo_root) -> tuple[str, str]:
    """Cria projeto + espaço e vincula o repositório; devolve (projectId, workspaceId)."""
    project = test_client.post("/api/projects", json={"name": "Git", "baseBranch": "main"}).json()
    workspace = test_client.post(
        f"/api/projects/{project['id']}/workspaces",
        json={"name": "Espaço", "branch": "feat/inicial"},
    ).json()
    response = test_client.post(
        f"/api/git/projects/{project['id']}/repository", json={"path": str(repo_root)}
    )
    assert response.status_code == 200, response.text
    return project["id"], workspace["id"]


def make_project_and_workspaces(test_client: TestClient) -> tuple[str, str, str]:
    project = test_client.post(
        "/api/projects",
        json={"name": "NIA", "objective": "Plataforma", "baseBranch": "main"},
    ).json()
    first = test_client.post(
        f"/api/projects/{project['id']}/workspaces",
        json={"name": "Canvas", "branch": "feat/canvas", "workDir": "C:/work/nia-canvas"},
    ).json()
    second = test_client.post(
        f"/api/projects/{project['id']}/workspaces",
        json={"name": "APIs", "branch": "feat/apis", "workDir": "C:/work/nia-apis"},
    ).json()
    return project["id"], first["id"], second["id"]
