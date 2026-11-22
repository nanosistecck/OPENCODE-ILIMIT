"""Configuração do aplicativo. O diretório de dados fica FORA das pastas dos projetos."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    worktrees_dir: Path
    host: str
    port: int
    git_timeout: int
    max_diff_chars: int
    logs_dir: Path
    prompts_dir: Path
    opencode_executable: str
    opencode_timeout: int
    remote_enabled: bool
    remote_public_origin: str
    remote_allowed_origins: tuple[str, ...]
    remote_password: str
    remote_session_hours: int
    remote_provider: str
    remote_identity_header: str

    @classmethod
    def from_env(cls) -> "Settings":
        raw = os.getenv("OCILIMIT_DATA_DIR")
        data_dir = Path(raw).expanduser() if raw else (Path.home() / ".opencode-ilimit" / "data")
        raw_worktrees = os.getenv("OCILIMIT_WORKTREES_DIR")
        worktrees = (
            Path(raw_worktrees).expanduser()
            if raw_worktrees
            else data_dir / "worktrees"
        )
        return cls(
            data_dir=data_dir,
            db_path=data_dir / "opencode-ilimit.db",
            worktrees_dir=worktrees,
            host=os.getenv("OCILIMIT_HOST", "127.0.0.1"),
            port=int(os.getenv("OCILIMIT_PORT", "8000")),
            git_timeout=int(os.getenv("OCILIMIT_GIT_TIMEOUT", "12")),
            max_diff_chars=int(os.getenv("OCILIMIT_MAX_DIFF_CHARS", "120000")),
            logs_dir=data_dir / "logs",
            prompts_dir=data_dir / "prompts",
            opencode_executable=os.getenv("OPENCODE_EXECUTABLE", ""),
            opencode_timeout=int(os.getenv("OPENCODE_TIMEOUT", "600")),
            remote_enabled=os.getenv("OCILIMIT_REMOTE_ENABLED", "0") in ("1", "true", "True"),
            remote_public_origin=os.getenv("OCILIMIT_PUBLIC_ORIGIN", ""),
            remote_allowed_origins=tuple(
                item.strip() for item in os.getenv("OCILIMIT_ALLOWED_ORIGINS", "").split(",") if item.strip()
            ),
            remote_password=os.getenv("OCILIMIT_REMOTE_PASSWORD", ""),
            remote_session_hours=int(os.getenv("OCILIMIT_SESSION_HOURS", "12")),
            remote_provider=os.getenv("OCILIMIT_TUNNEL_PROVIDER", "cloudflared"),
            remote_identity_header=os.getenv("OCILIMIT_IDENTITY_HEADER", "Cf-Access-Authenticated-User-Email"),
        )


settings = Settings.from_env()
