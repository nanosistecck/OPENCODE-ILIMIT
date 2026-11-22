from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_dict(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None
