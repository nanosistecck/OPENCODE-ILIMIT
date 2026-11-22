# OPENCODE ILIMIT — Descoberta de projetos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detectar automaticamente projeto, worktree, branch, remotos e base do PR a partir de uma pasta local e levar o usuário à fila do espaço correto.

**Architecture:** `app/discovery/service.py` reutiliza Git, GitHub CLI e OpenCode; preferências e vínculos em `0007_discovery.sql`. O frontend abre um diálogo compacto com resumo, escolhas curtas e ação **Ir para a fila**.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Git CLI; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-discovery-design.md`

## Global Constraints

- Descoberta inicial é somente leitura; nenhuma alteração de Git/arquivos.
- Preferência salva tem prioridade; origem dos dados é exibida.
- Branch atual, upstream e base do PR são distintos.
- GitHub indisponível não impede montar/executar fila local em worktree apta.
- Caminhos do Windows são operação local no modo remoto.

## Review Focus

1. Subpasta → raiz e reabertura do mesmo espaço — `test_subpasta_e_reabertura`.
2. Duas worktrees, mesmo projeto — `test_duas_worktrees_mesmo_projeto`.
3. Fork com publicação e base distintas — `test_fork_publicacao_e_base_pr_distintas`.
4. Preferência salva e fallback sem GitHub — `test_preferencia_salva_tem_prioridade`, `test_github_indisponivel_usa_dados_locais`.
5. Base sem worktree pronta e bloqueio remoto — `test_branch_base_nao_fica_pronta`, `test_caminho_local_bloqueado_no_remoto`.

---

### Task 1: Backend ✅

- [x] `0007_discovery.sql`, `app/discovery/service.py`, rotas `/api/discovery/...`, helper `default_branch`.

### Task 2: Testes ✅

- [x] 8 testes de descoberta + migração; backend total **56 aprovados** em lotes.

### Task 3: Frontend ✅

- [x] Tipos/adapter, diálogo **Abrir projeto** com resumo, escolhas, fontes e **Ir para a fila**; botões na sidebar e no cabeçalho.
- [x] Build e 5 testes aprovados.
- [x] Correções de smoke test: dedupe de remotos em `git remote -v` (sem escolha falsa/chaves duplicadas) e
  atualização periódica carregando espaços de todos os projetos (mantém o espaço aberto ativo).

### Task 4: Documentação ✅

- [x] README, api-contract (seção 13), design doc e plano.
