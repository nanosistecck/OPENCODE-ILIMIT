"""Migrações reproduzíveis. Cada arquivo NNNN_nome.sql é aplicado uma vez."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent
_MIGRATION = re.compile(r"^(\d{4})_.*\.sql$")


def migration_files() -> list[tuple[int, Path]]:
    items: list[tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = _MIGRATION.match(path.name)
        if match:
            items.append((int(match.group(1)), path))
    return sorted(items)


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    now = _utc_now()
    executed: list[int] = []
    for version, path in migration_files():
        if version in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, now),
        )
        executed.append(version)
    conn.commit()
    return executed


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
