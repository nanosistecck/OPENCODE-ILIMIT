# OPENCODE ILIMIT — Backend e persistência — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persistir projetos, espaços, mensagens, planos versionados e filas em SQLite local e conectar o frontend ao backend mantendo o modo demo.

**Architecture:** `backend/app/` separa `db/` (conexão + migrações), `domain/` (regras fora das rotas) e `api/` (schemas/rotas). No frontend, `HttpAdapter` implementa o mesmo `ExtendedAdapter` do `MockAdapter`; `AppProvider` alterna os dois.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, sqlite3, uvicorn, pytest/httpx; React/TypeScript/Vite no frontend.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-backend-design.md`

## Global Constraints

- Dados em `%USERPROFILE%\.opencode-ilimit\data`, sobrescrito por `OCILIMIT_DATA_DIR`.
- `PRAGMA foreign_keys = ON` em toda conexão; horários UTC; IDs estáveis.
- `workspaceId` é o vínculo; `branch` é exibição.
- Loopback por padrão; proxy Vite `/api`; WebSocket e execução reais ficam para o Prompt 03.
- Modo demonstração continua acessível; falha da API aparece como falha.

## Review Focus

1. Isolamento entre espaços — mensagem da branch A não aparece na B; teste: `test_persistence`.
2. Versões de plano — lote antigo preserva prompts e `sourceVersionId`; teste: `test_plan_versions`.
3. Reordenação inválida — conjunto divergente é rejeitado sem alterar a fila; teste: `test_queue`.
4. Reinício do backend — dados persistem após novo client; testes de persistência e fila.
5. API indisponível — banner de erro com retry/demo; verificação manual no navegador.

---

### Task 1: Fundação do backend ✅

- [x] `backend/requirements.txt`, `pytest.ini`, `app/config.py`, `app/db/connection.py`, `app/db/migrations.py`, `0001_initial.sql`.
- [x] Verificar: `python -m pytest` (migração, FK, health).

### Task 2: Regras de domínio ✅

- [x] `app/domain/projects.py`, `conversations.py`, `plans.py`, `batches.py`, `errors.py`, `utils.py`.
- [x] Validar dependências de plano e ordem exata na reordenação.

### Task 3: API HTTP ✅

- [x] `app/api/schemas.py`, `serializers.py`, `deps.py` e rotas de projects, workspaces, plans, batches e health.
- [x] `app/main.py` com CORS, lifespan e handler de `DomainError`.
- [x] Verificar: 13 testes aprovados.

### Task 4: HttpAdapter e alternância de modo ✅

- [x] `src/data/httpAdapter.ts`, `emptySnapshot.ts`, contrato ampliado em `adapter.ts`/`types.ts`.
- [x] `AppContext` com `mode`, `apiStatus`, troca de adaptador e `useMode()`.
- [x] Proxy `/api` no `vite.config.ts`; `ConnectionBanner` e `mode-switch`.

### Task 5: Telas e cadastro ✅

- [x] `SetupPanel` de projeto/espaços; editor de plano com nova versão; fila persistida e controls desabilitados no modo conectado; Git com metadados cadastrados.
- [x] Verificar: `npm run build`, `npm test`, navegação em 360 px.

### Task 6: Documentação ✅

- [x] `README.md`, `docs/api-contract.md` (status Prompt 02), design doc e este plano.
