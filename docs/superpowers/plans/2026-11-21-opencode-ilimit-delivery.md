# OPENCODE ILIMIT — Commit e PR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Revisar diff, selecionar arquivos, criar commit local, publicar branch e abrir PR em rascunho com vínculos persistidos e credenciais protegidas.

**Architecture:** `app/delivery/` separa comandos Git (`gitops.py`), integração `gh` com adaptador de teste (`github.py`) e orquestração com prévia/digest (`service.py`). Rotas `/api/delivery/...` validam vínculo e bloqueiam escrita durante execução da fila.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, Git CLI, GitHub CLI; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-delivery-design.md`

## Global Constraints

- Resolver pasta/branch/repositório pelo ID do espaço; revalidar antes de cada escrita.
- Escrita bloqueada com `QUEUE_BUSY` se a fila estiver ativa; leituras disponíveis.
- Prévia com digest; mudança externa exige nova revisão (`STALE_PREVIEW`).
- Preparados fora da seleção preservados (`STAGED_OUTSIDE_SELECTION`).
- Push sem force; resultado incerto consulta remoto antes de repetir.
- PR em rascunho por padrão; PR ativo reaproveitado; credenciais mascaradas.

## Review Focus

1. Commit seletivo — `test_commit_apenas_arquivo_selecionado`.
2. Índice externo preservado — `test_preparado_fora_da_selecao_preserva_indice`.
3. Prévia desatualizada — `test_previa_desatualizada_exige_revisao`.
4. Fila bloqueando escrita — `test_fila_bloqueia_escrita_mas_nao_consulta`.
5. Push/PR e recuperação — `test_push_publica_e_configura_upstream`, `test_pr_rascunho_base_diferente_e_existente`, `test_pr_incerto_consultar_antes_de_repetir`.

---

### Task 1: Migração e serviços ✅

- [x] `0005_delivery.sql`, `gitops.py`, `github.py`, `service.py` com digest, commit/push/PR e máscara.

### Task 2: Rotas ✅

- [x] `app/api/routes/delivery.py` registrada em `main.py`.

### Task 3: Testes ✅

- [x] 8 testes de entrega; backend total **42 aprovados**.

### Task 4: Frontend ✅

- [x] Tipos/adapter estendidos; painel **Entrega da branch** no Git com seleção, prévia, commit, push, PR e histórico.
- [x] Build e 5 testes aprovados.

### Task 5: Documentação e handoff ✅

- [x] README, api-contract (seção 11), design doc, plano e `docs/handoff/2026-11-21-prompt07-resumo.md`.
