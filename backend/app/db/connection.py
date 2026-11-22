"""Conexões SQLite com chaves estrangeiras habilitadas em TODA conexão."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from ..config import settings


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or settings.db_path
    target.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI executa dependências sync em pool de threads: a conexão pode ser
    # criada e fechada em threads diferentes.
    conn = sqlite3.connect(target, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependência FastAPI: confirma ao sair ou desfaz em caso de erro."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
