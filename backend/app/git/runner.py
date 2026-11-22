"""Único ponto de chamada ao git. Argumentos separados, timeout e saída controlada."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ..config import settings


@dataclass(frozen=True)
class GitResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    error: str = ""

    @property
    def text(self) -> str:
        return self.stdout.strip()


def run_git(
    args: list[str],
    cwd: str | None = None,
    timeout: int | None = None,
) -> GitResult:
    """Executa git com lista de argumentos (nunca shell=True)."""
    command = ["git", *args]
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            timeout=timeout or settings.git_timeout,
            check=False,
        )
    except FileNotFoundError:
        return GitResult(False, "", "", -1, "Git não está instalado ou não está no PATH do backend.")
    except subprocess.TimeoutExpired:
        return GitResult(False, "", "", -2, f"Git excedeu o limite de {timeout or settings.git_timeout}s.")
    except OSError as exc:
        return GitResult(False, "", "", -3, f"Falha ao iniciar o git: {exc}")

    stdout = process.stdout.decode("utf-8", errors="replace")
    stderr = process.stderr.decode("utf-8", errors="replace")
    return GitResult(
        ok=process.returncode == 0,
        stdout=stdout,
        stderr=stderr,
        returncode=process.returncode,
        error="" if process.returncode == 0 else (stderr.strip() or stdout.strip() or f"git saiu com {process.returncode}"),
    )
