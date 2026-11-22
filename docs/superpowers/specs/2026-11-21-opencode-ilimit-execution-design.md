# Design — Integração OpenCode e motor da fila (Prompt 04)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Executar lotes localmente no backend, com verificação Git por tentativa, estados confirmados,
log persistente e recuperação após reinício. O painel passa a controlar a fila real; o modo
demonstração permanece explícito.

## Objetivos

- Integrar a CLI do OpenCode com saída estruturada, capacidades e diagnóstico explícito.
- Motor assíncrono com no máximo uma execução ativa por workspace.
- Verificar Git antes de cada tentativa (pasta, repositório, branch, HEAD, conflitos, operações).
- Persistir tentativas, prompt efetivo, sessão, modelos, HEADs e log; leitura incremental.
- Pausa em duas fases, cancelamento confirmado, retry e continuação de sessão.

## Não-objetivos

- Commit/push/PR, WebSocket, acesso remoto, chat/análise/planejamento (Prompt 05).

## Anti-objetivos

- Repetir automaticamente uma tentativa interrompida.
- Considerar código de saída zero como sucesso sem confirmação estruturada.
- Truncar prompts longos.

## Restrições

- Git e OpenCode no PATH do **backend** (ou `OPENCODE_EXECUTABLE`).
- Argumentos separados, nunca shell interpolado; timeout configurável.
- Windows: encerrar processo com `terminate()`/`kill()` e confirmar término.
- IDs estáveis, `workspace_id` como vínculo, caminhos relativos na API.

## Abordagens consideradas

1. **Execução no frontend com timers** — perde o trabalho ao fechar a aba e não garante uma
   execução por worktree. Descartada.
2. **Biblioteca SDK proprietária** — a CLI instalada expõe `run --format json`; dependência extra
   e contrato instável. Descartada.
3. **`app/opencode/client.py` + `app/queue/engine.py` (escolhida)** — CLI com saída estruturada,
   motor assíncrono no backend e persistência SQLite; o mesmo cliente serve o Prompt 05.

## Decisões

- `attempts` é uma tabela nova (migração `0003_queue.sql`), separada do estado do lote.
- `depends_on` e `acceptance_criteria` foram copiados para `batch_items` na geração da fila.
- Sucesso exige evento de conclusão reconhecido + ausência de erro; caso contrário `inconclusive`.
- Log em arquivo por tentativa com `offset`/`nextOffset` — sem recarregar o arquivo inteiro.
- Locks por workspace + checagem de status do lote bloqueiam duas abas.
- `recover_interrupted` roda no startup e nunca repete tentativa; PID possivelmente vivo gera
  `PREVIOUS_PROCESS_ALIVE`.
- Prompt > 30.000 bytes retorna `PROMPT_TOO_LARGE` sem truncar (limite do transporte Windows).
- `session_id` retornado pelo OpenCode fica na tentativa; `retry(continueSession=true)` reusa.

## Verificação real

OpenCode v2.3.2 detectado; capacidades lidas de `opencode run --help`. O diagnóstico real retornou
`provider.auth / 401 API key not valid` — limitação de credencial local, registrada. A fila foi
validada com executável simulador e cliente determinístico (27 testes de backend).

## O que fica para o Prompt 05

Chat, análise e planejamento devem reutilizar `OpenCodeClient` e o vínculo de sessão por
`workspace_id`/`batch_id`/`attempt_id`.
