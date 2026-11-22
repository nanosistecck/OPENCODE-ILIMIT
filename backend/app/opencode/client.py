"""Cliente OpenCode: detecção, capacidades, diagnóstico e execução assíncrona."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..config import settings
from ..domain.errors import DomainError

MAX_PROMPT_BYTES = 30_000


@dataclass
class RunResult:
    status: str  # success | failure | inconclusive | cancelled
    session_id: str = ""
    exit_code: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    error: str = ""
    final_text: str = ""

    @property
    def output(self) -> str:
        return "\n".join(self.raw_lines)


class OpenCodeClient:
    """Único ponto de chamada à CLI. Nunca interpola prompt em shell."""

    def __init__(self, executable: str = "") -> None:
        self.executable = executable or settings.opencode_executable or (shutil.which("opencode") or "")

    def detect(self) -> dict[str, Any]:
        path = self.executable
        source = "configurado"
        if not path:
            candidates = [
                Path(os.environ.get("APPDATA", "")) / "npm" / "opencode.cmd",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ai.opencode.desktop" / "opencode.cmd",
            ]
            path = next((str(item) for item in candidates if item.exists()), "")
            source = "auto-detectado" if path else "não encontrado"
        return {
            'found': bool(path),
            'path': path,
            'source': source,
            'version': self.version(path) if path else '',
        }

    def version(self, executable: str | None = None) -> str:
        exe = executable or self.executable
        if not exe:
            return ''
        try:
            process = subprocess.run(
                [exe, "--version"], capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DomainError(f"Falha ao consultar versão do OpenCode: {exc}", code='OPENCODE_FAILED') from exc
        text = (process.stdout or process.stderr).strip()
        if process.returncode != 0:
            raise DomainError(f"OpenCode --version falhou: {text}", code='OPENCODE_FAILED')
        return text

    def capabilities(self) -> dict[str, Any]:
        if not self.executable:
            return {'found': False, 'flags': [], 'jsonFormat': False, 'session': False,
                    'model': False, 'agent': False, 'file': False}
        try:
            process = subprocess.run(
                [self.executable, "run", "--help"], capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DomainError(f"Falha ao consultar capacidades: {exc}", code='OPENCODE_FAILED') from exc
        help_text = process.stdout or ''
        flags = sorted({
            token.strip().rstrip(',')
            for token in help_text.split()
            if token.startswith('--')
        })
        return {
            'found': True,
            'flags': flags,
            'jsonFormat': '--format' in flags,
            'session': '--session' in flags,
            'model': '--model' in flags,
            'agent': '--agent' in flags,
            'file': '--file' in flags,
            'text': help_text,
        }

    def diagnostic(self, cwd: str | None = None) -> dict[str, Any]:
        """Ação explícita: envia um prompt simples e devolve a saída bruta."""
        if not self.executable:
            raise DomainError('OpenCode não encontrado neste computador.', code='OPENCODE_NOT_FOUND')
        try:
            process = subprocess.run(
                [self.executable, "run", "--format", "json", "--standalone",
                 "--", "Responda apenas com a palavra ILIMIT."],
                cwd=cwd or str(settings.data_dir), capture_output=True, text=True,
                timeout=90, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DomainError(f"Diagnóstico falhou: {exc}", code='OPENCODE_FAILED') from exc
        return {
            'exitCode': process.returncode,
            'stdout': process.stdout[:50_000],
            'stderr': process.stderr[:10_000],
        }

    @staticmethod
    def validate_prompt(prompt: str) -> None:
        size = len(prompt.encode('utf-8'))
        if size > MAX_PROMPT_BYTES:
            raise DomainError(
                f'Prompt com {size} bytes excede o limite de {MAX_PROMPT_BYTES} bytes '
                'para transporte pela CLI do Windows. O texto não foi truncado; divida o item.',
                code='PROMPT_TOO_LARGE', status=422,
            )

    async def run(
        self,
        prompt: str,
        cwd: str,
        *,
        session_id: str = '',
        model: str = '',
        agent: str = '',
        on_line: Callable[[str], Awaitable[None]] | None = None,
        timeout: int | None = None,
        process_holder: dict[str, Any] | None = None,
    ) -> RunResult:
        if not self.executable:
            raise DomainError('OpenCode não encontrado neste computador.', code='OPENCODE_NOT_FOUND')
        self.validate_prompt(prompt)
        args = [self.executable, "run", "--format", "json", "--standalone"]
        if session_id:
            args += ["--session", session_id]
        if model:
            args += ["--model", model]
        if agent:
            args += ["--agent", agent]
        args += ["--", prompt]

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process_holder is not None:
            process_holder['process'] = process
            process_holder['pid'] = process.pid
        result = RunResult(status='inconclusive')
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        completion = False
        final_text: list[str] = []

        async def consume(stream, is_stdout: bool) -> None:
            nonlocal completion
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode('utf-8', errors='replace').rstrip('\r\n')
                result.raw_lines.append(('out ' if is_stdout else 'err ') + text)
                if on_line:
                    await on_line(('out ' if is_stdout else 'err ') + text + '\n')
                if not is_stdout:
                    if text.strip():
                        errors.append(text.strip())
                    continue
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    if text.strip():
                        final_text.append(text.strip())
                    continue
                if isinstance(event, dict):
                    events.append(event)
                    sid = event.get('sessionID') or event.get('session_id')
                    if sid and not result.session_id:
                        result.session_id = str(sid)
                    kind = str(event.get('type', ''))
                    if kind == 'error' or event.get('isError') or (isinstance(event.get('error'), dict) and event['error']):
                        errors.append(json.dumps(event, ensure_ascii=False)[:1000])
                    if kind in ('result', 'session.idle', 'step_finish', 'turn_completed'):
                        status_value = str(event.get('status') or event.get('state') or '').lower()
                        part = event.get('part')
                        if isinstance(part, dict):
                            inner = part.get('state')
                            if isinstance(inner, dict):
                                status_value = str(inner.get('status') or status_value)
                        if status_value in ('success', 'completed', 'done') or kind in ('result', 'session.idle'):
                            completion = True
                    text_value = event.get('text') or event.get('content')
                    if isinstance(text_value, str) and text_value.strip():
                        final_text.append(text_value.strip())

        try:
            await asyncio.wait_for(
                asyncio.gather(consume(process.stdout, True), consume(process.stderr, False)),
                timeout=timeout or settings.opencode_timeout,
            )
            result.exit_code = await process.wait()
        except asyncio.TimeoutError:
            await terminate(process)
            result.status = 'cancelled'
            result.error = f'Timeout após {timeout or settings.opencode_timeout}s; execução encerrada.'
            return result

        result.events = events
        result.final_text = "\n".join(final_text[-20:])
        if errors:
            result.status = 'failure'
            result.error = " | ".join(errors[-5:])[:4000]
        elif not completion:
            result.status = 'inconclusive'
            result.error = 'Saída sem confirmação estruturada de conclusão; avanço bloqueado.'
        else:
            result.status = 'success'
        return result


async def terminate(process: asyncio.subprocess.Process) -> None:
    """Encerra pelo mecanismo suportado no Windows e confirma o término."""
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except (ProcessLookupError, OSError):
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=8)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except (ProcessLookupError, OSError):
            pass
        await process.wait()
