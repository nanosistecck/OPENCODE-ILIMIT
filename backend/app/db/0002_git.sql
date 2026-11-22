-- Git local e worktrees. Registros antigos ficam com git_status = 'pending'.

ALTER TABLE projects ADD COLUMN git_repo_root TEXT;
ALTER TABLE projects ADD COLUMN git_common_dir TEXT;
ALTER TABLE projects ADD COLUMN git_linked_at TEXT;

ALTER TABLE workspaces ADD COLUMN git_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE workspaces ADD COLUMN git_repo_root TEXT;
ALTER TABLE workspaces ADD COLUMN git_common_dir TEXT;
ALTER TABLE workspaces ADD COLUMN git_work_dir TEXT;
ALTER TABLE workspaces ADD COLUMN git_branch TEXT;
ALTER TABLE workspaces ADD COLUMN base_ref TEXT;
ALTER TABLE workspaces ADD COLUMN origin_commit TEXT;
ALTER TABLE workspaces ADD COLUMN bound_head TEXT;
ALTER TABLE workspaces ADD COLUMN git_linked_at TEXT;
ALTER TABLE workspaces ADD COLUMN git_error TEXT;
