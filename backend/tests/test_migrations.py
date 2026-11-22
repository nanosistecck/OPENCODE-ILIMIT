from fastapi.testclient import TestClient

from app.db.connection import connect
from app.db.migrations import run_migrations


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_migrations_criam_tabelas_e_sao_idempotentes(client: TestClient) -> None:
    conn = connect()
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        assert {
            "projects", "workspaces", "conversations", "messages", "plans",
            "plan_versions", "plan_steps", "batches", "batch_items", "schema_migrations",
        } <= tables
        assert run_migrations(conn) == []
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
        assert versions == [1, 2, 3, 4, 5, 6, 7]
    finally:
        conn.close()


def test_foreign_keys_habilitadas_em_toda_conexao(client: TestClient) -> None:
    conn = connect()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_vinculo_cross_entity_e_rejeitado_pelo_banco(client: TestClient) -> None:
    conn = connect()
    try:
        import pytest

        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO messages (id, conversation_id, workspace_id, role, content, position, status, created_at) "
                "VALUES ('msg_x', 'conv_inexistente', 'ws_inexistente', 'user', 'x', 1, 'sent', '2026-01-01T00:00:00Z')"
            )
    finally:
        conn.close()
