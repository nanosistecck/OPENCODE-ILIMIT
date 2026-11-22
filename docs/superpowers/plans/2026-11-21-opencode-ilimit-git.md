# OPENCODE ILIMIT — Git local — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Vincular repositório, branch e worktree verificada a cada espaço, com status/diff reais e verificação reutilizável para o motor de fila.

**Architecture:** `backend/app/git/` separa subprocess (`runner`), consultas (`local`) e orquestração com SQLite/locks (`service`). Rotas `/api/git/...` expõem probe, overview, criação/abertura, status, diff e verify. No frontend, `HttpAdapter` ganha os métodos do contrato e o painel Git renderiza dados reais no modo conectado.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, Git CLI (porcelain), pytest; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-git-design.md`

## Global Constraints

- Git no PATH do backend; argumentos separados; timeout configurável; UTF-8 tolerante.
- Worktrees em `OCILIMIT_WORKTREES_DIR`; nomes válidos no Windows.
- Preservar IDs, chats, planos, lotes e histórico; espaços antigos → `git_status = pending`.
- Modo demo preservado; falha da API aparece como falha; caminhos relativos na API.
- Commit/push/PR/execução/WebSocket/túnel fora do escopo.

## Review Focus

1. Isolamento de worktrees — alterações em uma não aparecem na outra; teste: `test_status_e_diff_isolados`.
2. Preservação da pasta original — branch/HEAD inalterados após criar worktrees; teste: `test_criar_duas_worktrees`.
3. Recuperação pós-falha do banco — worktree reaproveitada, sem duplicar; teste: `test_recuperacao`.
4. Motivos de verificação — branch trocada/HEAD destacado/pasta ausente; teste: `test_verificacao_motivos`.
5. Segurança de caminho no diff — `../` rejeitado; teste: `test_diff_rejeita_caminho_fora_da_pasta`.

---

### Task 1: Migração e base Git ✅

- [x] `backend/app/db/0002_git.sql` com campos de vínculo e `git_status DEFAULT 'pending'`.
- [x] `config.py` com `worktrees_dir`, `git_timeout`, `max_diff_chars`.
- [x] `git/runner.py`, `git/local.py` (probe/refs/worktrees/status/diff/verify).

### Task 2: Serviço e rotas ✅

- [x] `git/service.py`: vínculo, criação/abertura, locks, transações, recuperação, verify.
- [x] `api/routes/git.py`, schemas e serializers atualizados; `main.py` inclui o router.

### Task 3: Testes com repositórios descartáveis ✅

- [x] Fixture `git_repo` e 8 testes Git; total backend 21 aprovados.

### Task 4: Frontend ✅

- [x] Tipos Git, `ExtendedAdapter`, `HttpAdapter` e stubs no `MockAdapter`.
- [x] Painel Git conectado: vínculo, bases/refs, criar/abrir, status, diff, verificação, recovery.
- [x] Cadastro manual de worktree removido do SetupPanel (subsistiu só o registro do espaço).
- [x] `npm run build`, `npm test` e checagem em 360 px aprovados.

### Task 5: Documentação ✅

- [x] `README.md`, `docs/api-contract.md` (seção 8 + operação verify), design doc e este plano.
