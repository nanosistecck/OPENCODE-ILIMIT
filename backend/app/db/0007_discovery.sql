-- Preferências de descoberta e vínculos por espaço.

CREATE TABLE IF NOT EXISTS project_discovery_preferences (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    base_branch TEXT NOT NULL DEFAULT '',
    publish_remote TEXT NOT NULL DEFAULT '',
    pr_repository TEXT NOT NULL DEFAULT '',
    pr_base TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT 'usuario'
);

CREATE TABLE IF NOT EXISTS workspace_discovery (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    root TEXT NOT NULL DEFAULT '',
    common_dir TEXT NOT NULL DEFAULT '',
    observed_head TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'local',
    updated_at TEXT NOT NULL
);
