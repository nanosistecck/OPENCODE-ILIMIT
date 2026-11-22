"""Controle local do acesso remoto (kill switch em memória)."""

from ..config import settings

_active = settings.remote_enabled


def remote_active() -> bool:
    return _active


def set_remote_active(value: bool) -> None:
    global _active
    _active = bool(value)
