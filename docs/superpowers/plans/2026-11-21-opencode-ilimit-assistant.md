# OPENCODE ILIMIT — Chat e planejamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrar chat, análise, proposta validada, aprovação de versão, geração de lote e revisão de critérios ao fluxo existente.

**Architecture:** `app/assistant/service.py` centraliza os fluxos reutilizando `OpenCodeClient`, `git.service.verify`, regras de plano/lote e o estado do motor. Rotas `/api/assistant/...` expõem operações; o painel conectado faz polling do estado e permite revisar/aprovar/editar.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, asyncio; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-assistant-design.md`

## Global Constraints

- Persistir mensagem antes de enviar; resposta parcial e erro preservados.
- Sessão de planejamento separada da sessão do lote; vínculo por `workspace_id`.
- Proposta inválida não gera lote; dependências validadas com regras do Prompt 02.
- Aprovação cria nova versão imutável; lote idempotente por versão salvo `force`.
- Revisão distingue verificado/pendente/sem evidência; modo demo preservado.

## Review Focus

1. Isolamento de chat entre branches — `test_chat_isolado_por_espaco`.
2. Proposta válida e lote íntegro — `test_analise_proposta_aprovacao_e_lote`.
3. Proposta inválida/cíclica sem lote — `test_proposta_invalida_nao_gera_lote`, `test_dependencia_ciclica_e_rejeitada`.
4. Edição após lote preserva origem — `test_nova_versao_preserva_lote`.
5. Recuperação de sessão e revisão de lacuna — `test_nova_sessao_preserva_mensagens`, `test_revisao_aponta_criterio_pendente`.

---

### Task 1: Migração e serviços ✅

- [x] `0004_assistant.sql`, `app/assistant/service.py` com chat/analysis/proposal/approve/batch/review.
- [x] Validação de JSON e de dependências reaproveitando `plans.validate_steps`.

### Task 2: Rotas ✅

- [x] `app/api/routes/assistant.py` registrada em `main.py`.

### Task 3: Testes ✅

- [x] 7 testes de assistente com `AssistantFake`; backend total **34 aprovados**.

### Task 4: Frontend ✅

- [x] Tipos/adapter estendidos; painel conectado de chat + análise + proposta + revisão.
- [x] Build, 5 testes e verificação em 360 px aprovados.

### Task 5: Documentação e handoff ✅

- [x] README, api-contract (seção 10), design doc, plano e `docs/handoff/2026-11-21-prompt06-resumo.md`.
