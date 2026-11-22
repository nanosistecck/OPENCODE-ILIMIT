"""Erros de regra de negócio, convertidos em HTTP pelo handler da API."""

from __future__ import annotations


class DomainError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "INVALID_STATE",
        status: int = 409,
        detail: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.detail = detail or {}


class NotFoundError(DomainError):
    def __init__(self, message: str = "Recurso não encontrado.", code: str = "NOT_FOUND") -> None:
        super().__init__(message, code=code, status=404)
