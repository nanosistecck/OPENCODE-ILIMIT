-- Acesso remoto: sessões, eventos sequenciados, idempotência e auditoria.

CREATE TABLE IF NOT EXISTS remote_sessions (
    token_hash TEXT PRIMARY KEY,
    user_label TEXT NOT NULL DEFAULT 'remoto',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_seen_at TEXT,
    csrf TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    type TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_workspace_sequence ON app_events(workspace_id, sequence);

CREATE TABLE IF NOT EXISTS remote_operations (
    request_key TEXT PRIMARY KEY,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status INTEGER NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS remote_audit (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_label TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    status INTEGER NOT NULL,
    request_key TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_remote_audit_created ON remote_audit(created_at);
