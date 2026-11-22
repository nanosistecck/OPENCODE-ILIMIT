-- Vínculos de entrega: commits, publicação e pull requests.

CREATE TABLE IF NOT EXISTS delivery_commits (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    batch_id TEXT,
    attempt_id TEXT,
    hash TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    files TEXT NOT NULL DEFAULT '[]',
    head_before TEXT NOT NULL DEFAULT '',
    head_after TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delivery_commits_workspace ON delivery_commits(workspace_id, created_at);

CREATE TABLE IF NOT EXISTS delivery_pushes (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    commit_id TEXT REFERENCES delivery_commits(id) ON DELETE SET NULL,
    remote TEXT NOT NULL DEFAULT '',
    branch TEXT NOT NULL DEFAULT '',
    upstream TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pushed',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_pull_requests (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    commit_id TEXT REFERENCES delivery_commits(id) ON DELETE SET NULL,
    number INTEGER,
    url TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'open',
    source TEXT NOT NULL DEFAULT '',
    target TEXT NOT NULL DEFAULT '',
    repository TEXT NOT NULL DEFAULT '',
    draft INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    last_state TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delivery_prs_workspace ON delivery_pull_requests(workspace_id, created_at);
