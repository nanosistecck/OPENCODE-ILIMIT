# OPENCODE ILIMIT — Acesso remoto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Servir painel e API na mesma origem pública com sessão, CSRF, eventos sequenciados, reconexão e idempotência, mantendo o modo local intacto.

**Architecture:** `app/remote/` concentra auth, eventos, middleware guard e rotas HTTP/WebSocket. O frontend usa um `RemoteProvider` com cursor de sequência, resync e banner de login/reconexão.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, WebSocket; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-remote-design.md`

## Global Constraints

- Remoto desativado por padrão; kill switch local; backend em loopback.
- Sessão HttpOnly/SameSite=Strict/Secure em HTTPS; CSRF nas escritas; expiração e revogação.
- Eventos com `sequence` do backend, `workspaceId` no contexto e replay por `after`.
- Idempotência por `Idempotency-Key`; auditoria sem credenciais.
- Ações de configuração/caminhos do Windows permanecem locais.

## Review Focus

1. Remoto desativado e acesso local — `test_remote_desativado_por_padrao`.
2. Login, cookie, CSRF e logout — `test_login_cookie_csrf_e_logout`.
3. Revogação — `test_sessao_expirada_ou_revogada_nao_acessa`.
4. Eventos sequenciados e isolamento — `test_eventos_sequencia_e_isolamento`.
5. Idempotência e WebSocket — `test_idempotencia_de_escrita`, `test_websocket_envia_snapshot_e_evento`.

---

### Task 1: Backend ✅

- [x] `0006_remote.sql`, `app/remote/{auth,events,middleware,routes,state}.py`, estáticos em `main.py`.

### Task 2: Testes ✅

- [x] 6 testes de remoto; backend total 48 testes.

### Task 3: Frontend ✅

- [x] Tipos/adapter, `RemoteProvider` com WS + resync, `RemoteBanner`, idempotência e CSRF no `HttpAdapter`.
- [x] Build e 5 testes aprovados.

### Task 4: Documentação ✅

- [x] README, api-contract (seção 12), design doc e plano.
