# OPENCODE ILIMIT — Execução e OpenCode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Executar lotes no backend com OpenCode local, persistindo tentativas e permitindo pausa, cancelamento, retry e recuperação.

**Architecture:** `app/opencode/client.py` centraliza a CLI (detecção, capacidades, diagnóstico, execução assíncrona e cancelamento). `app/queue/engine.py` orquestra execução por workspace com verificação Git, locks e transições de estado. Rotas `/api/queue/...` expõem controles e leitura incremental de log; o painel faz polling.

**Tech Stack:** Python 3.11+, FastAPI, asyncio/subprocess, SQLite; React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-execution-design.md`

## Global Constraints

- CLI com argumentos separados, timeout e UTF-8; prompt > 30.000 bytes rejeitado sem truncar.
- Verificação Git (`git.service.verify`) antes de cada tentativa; pasta resolvida pelo ID do espaço.
- Uma execução ativa por workspace; sucesso exige evento estruturado e ausência de erro.
- Nenhuma repetição automática após interrupção; pausa solicitada ≠ confirmada.
- Modo demo preservado; modo conectado mostra só estados confirmados.

## Review Focus

1. Sequência estrita de tentativas — teste: `test_executa_tres_prompts_em_sequencia`.
2. Falha na segunda etapa e retry — teste: `test_falha_mantem_terceiro_pendente_e_retry`.
3. Duas abas — teste: `test_segunda_aba_nao_inicia_duplicado`.
4. Pausa/recuperação — testes: `test_pause_termina_etapa_e_sobrevive_a_reinicio`, `test_recuperacao_sem_repeticao_automatica`.
5. Erro com exit 0 e prompt longo — testes: `test_erro_com_codigo_zero_bloqueia`, `test_prompt_longo_e_rejeitado_sem_truncar`.

---

### Task 1: Integração OpenCode ✅

- [x] `app/opencode/client.py` com detect/version/capabilities/diagnostic/run assíncrono e `terminate`.
- [x] Capacidades lidas de `opencode run --help`; OpenCode v2.3.2 detectado no Windows.

### Task 2: Migração e persistência ✅

- [x] `0003_queue.sql`: `attempts`, `depends_on`, `acceptance_criteria`, campos de controle e `app_settings`.
- [x] `app/queue/persistence.py`: settings, tentativas, estado do lote, log por offset e `recover_interrupted`.

### Task 3: Motor ✅

- [x] `app/queue/engine.py`: locks por workspace, verificação Git por tentativa, pausa/cancel/retry/continue.
- [x] Rotas `/api/queue/...` e recuperação no startup.

### Task 4: Testes ✅

- [x] Fixture `fake_opencode` (saída estruturada, atraso, falha) e `FakeClient` determinístico.
- [x] Backend: **27 testes aprovados**.

### Task 5: Frontend ✅

- [x] Tipos de fila/tentativa/OpenCode; `HttpAdapter` e `MockAdapter` estendidos.
- [x] Painel conectado com polling, log incremental, configuração/diagnóstico e ações de retry.
- [x] `npm run build`, `npm test` e verificação em 360 px aprovados.

### Task 6: Documentação ✅

- [x] README, api-contract (seção 9), design doc e este plano.
