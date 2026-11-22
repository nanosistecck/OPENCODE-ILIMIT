-- Motor da fila: tentativas persistidas, dependências e configuração do OpenCode.

ALTER TABLE batch_items ADD COLUMN depends_on TEXT NOT NULL DEFAULT '[]';
ALTER TABLE batch_items ADD COLUMN acceptance_criteria TEXT NOT NULL DEFAULT '';

ALTER TABLE batches ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE batches ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE batches ADD COLUMN current_attempt_id TEXT;
ALTER TABLE batches ADD COLUMN block_reason TEXT;
ALTER TABLE batches ADD COLUMN last_error TEXT;
ALTER TABLE batches ADD COLUMN resume_session TEXT;
ALTER TABLE batches ADD COLUMN resume_of TEXT;

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES batch_items(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id TEXT,
    prompt_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    status TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    log_path TEXT NOT NULL DEFAULT '',
    pid INTEGER,
    head_before TEXT,
    head_after TEXT,
    git_status_before TEXT,
    git_status_after TEXT,
    requested_model TEXT,
    observed_model TEXT,
    requested_agent TEXT,
    exit_code INTEGER,
    events TEXT NOT NULL DEFAULT '[]',
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    resume_of TEXT,
    acceptance_criteria TEXT,
    branch TEXT,
    work_dir TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_batch ON attempts(batch_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_workspace ON attempts(workspace_id, created_at);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
