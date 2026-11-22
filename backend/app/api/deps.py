"""Dependências compartilhadas das rotas."""

from ..db.connection import get_db

__all__ = ["get_db"]
