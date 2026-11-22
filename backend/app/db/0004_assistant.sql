-- Chat, análise, propostas de plano e revisão de entrega.

ALTER TABLE conversations ADD COLUMN session_id TEXT;
ALTER TABLE conversations ADD COLUMN session_kind TEXT NOT NULL DEFAULT 'chat';
ALTER TABLE conversations ADD COLUMN session_status TEXT NOT NULL DEFAULT 'none';
ALTER TABLE conversations ADD COLUMN summary TEXT NOT NULL DEFAULT '';
ALTER TABLE conversations ADD COLUMN updated_at TEXT;

ALTER TABLE messages ADD COLUMN chat_attempt_id TEXT;
ALTER TABLE messages ADD COLUMN session_id TEXT;
ALTER TABLE messages ADD COLUMN error TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN partial TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat';

ALTER TABLE plans ADD COLUMN source_analysis_id TEXT;
ALTER TABLE plans ADD COLUMN source_proposal_id TEXT;
ALTER TABLE plans ADD COLUMN branch TEXT;
ALTER TABLE plans ADD COLUMN approved_at TEXT;

CREATE TABLE IF NOT EXISTS plan_proposals (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    message_id TEXT,
    analysis_id TEXT,
    status TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    decisions TEXT NOT NULL DEFAULT '[]',
    questions TEXT NOT NULL DEFAULT '[]',
    steps TEXT NOT NULL DEFAULT '[]',
    validation_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proposals_workspace ON plan_proposals(workspace_id, created_at);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    message_id TEXT,
    content TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '[]',
    assumptions TEXT NOT NULL DEFAULT '[]',
    questions TEXT NOT NULL DEFAULT '[]',
    git_state TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    batch_id TEXT,
    version_id TEXT,
    report TEXT NOT NULL DEFAULT '{}',
    head_before TEXT,
    head_after TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_workspace ON reviews(workspace_id, created_at);
