# Contrato de integração — OPENCODE ILIMIT

Versão 0.1 (Prompt 01). Este documento descreve o contrato que o frontend já consome
via `Adapter` (`src/data/adapter.ts`) e que o backend Python/FastAPI deverá implementar
no Prompt 02. **Todos os caminhos são relativos** à origem da aplicação.

## 1. Princípios de vínculo

- `projectId`, `workspaceId`, `batchId` e `attemptId` são **IDs estáveis**.
- `workspaceId` vincula conversa, plano, fila/lote e histórico.
- `branch` é **informação de exibição**; o vínculo entre entidades é sempre o ID.
- Nenhuma mutação confia em sequência gerada pelo cliente.

## 2. Recursos e caminhos relativos

| Método | Caminho | Uso no frontend |
| --- | --- | --- |
| `GET` | `/api/projects` | Sidebar de projetos |
| `GET` | `/api/projects/{projectId}/workspaces` | Lista de branches/worktrees |
| `GET` | `/api/workspaces/{workspaceId}/state` | Estado agregado do espaço |
| `GET` | `/api/workspaces/{workspaceId}/conversations` | Chat |
| `POST` | `/api/workspaces/{workspaceId}/messages` | Enviar mensagem |
| `GET` | `/api/workspaces/{workspaceId}/plan` | Plano e versões |
| `POST` | `/api/workspaces/{workspaceId}/plan/review` | Revisar plano |
| `POST` | `/api/workspaces/{workspaceId}/queue` | Gerar fila a partir do plano |
| `GET` | `/api/workspaces/{workspaceId}/batches` | Lotes do espaço |
| `POST` | `/api/batches/{batchId}/items` | Adicionar prompts/arquivos |
| `PATCH` | `/api/batches/{batchId}/items/{itemId}` | Editar item |
| `DELETE` | `/api/batches/{batchId}/items/{itemId}` | Remover item |
| `POST` | `/api/batches/{batchId}/items/{itemId}/move` | Reordenar (`direction: -1 \| 1`) |
| `POST` | `/api/batches/{batchId}/start` | Iniciar lote |
| `POST` | `/api/batches/{batchId}/pause` | **Solicitar** pausa |
| `POST` | `/api/batches/{batchId}/resume` | Retomar/corrigir |
| `POST` | `/api/batches/{batchId}/cancel` | Cancelar |
| `GET` | `/api/workspaces/{workspaceId}/attempts` | Histórico do espaço |
| `GET` | `/api/workspaces/{workspaceId}/git` | Diff/commits/PR (simulados no demo) |
| `GET` | `/api/events?after={sequence}` | Eventos perdidos após reconexão |

Respostas de mutação devem devolver o recurso atualizado para que o frontend
reconcilie o cache. Erros usam `{ "code": "DISCONNECTED" | "NOT_FOUND" | "INVALID_STATE", "message": "..." }`.

## 3. Eventos

Envelope obrigatório:

```json
{
  "sequence": 123,
  "id": "evt-9f2c",
  "type": "batch.paused.confirmed",
  "context": {
    "workspaceId": "ws-canvas",
    "projectId": "prj-nia",
    "batchId": "batch-canvas-demo",
    "attemptId": "attempt-42",
    "conversationId": null
  },
  "createdAt": "2026-11-21T10:15:30.000Z",
  "summary": "Pausa confirmada após a etapa atual"
}
```

- `sequence`: **atribuído pelo backend**, monotonicamente crescente. É o cursor de
  reconexão e a garantia de ordem. O demo gera localmente apenas para fins de exibição.
- `context`: sempre contém `workspaceId`; os demais campos são opcionais e identificam
  o recurso afetado.
- `type`: um dos valores de `EventType` em `src/domain/types.ts` (ex.:
  `workspace.changed`, `message.created`, `queue.generated`, `batch.started`,
  `batch.paused.requested`, `batch.paused.confirmed`, `attempt.finished`,
  `connection.changed`).

### Ação solicitada ≠ resultado confirmado

`POST /api/batches/{id}/pause` responde `202` com `status: "pausing"` e emite
`batch.paused.requested`. A confirmação **só** ocorre quando a etapa atual termina,
via `batch.paused.confirmed` (status `paused`). A interface exibe os dois rótulos de
forma distinta — "Pausa solicitada" e "Pausado (confirmado)".

Regra de falha: se a etapa falhar, `attempt.finished` é emitido com `status=failure`,
o cursor permanece na etapa falha e as seguintes continuam `pending` até `resume`
ou correção do fluxo.

## 4. Transporte em tempo real (reservado)

O WebSocket real **não é implementado nesta etapa**. Contrato previsto:

- Conexão: `WS /ws/events?workspaceId={workspaceId}&after={lastSequence}`.
- Na reconexão, o cliente envia o último `sequence` recebido; o backend reenvia os
  eventos posteriores em ordem.
- While desconectado, o frontend preserva o último snapshot recebido e desabilita
  ações que dependem do PC (`start`, `pause`, `resume`, `cancel`, envio de mensagem,
  revisão/geração de fila).
- Troca de espaço reinscreve o canal para o novo `workspaceId`.

## 5. Estados que o backend deve prever

| Estado | Contrato |
| --- | --- |
| Conexão | `connected \| connecting \| disconnected \| error`; em `disconnected`, manter último estado visível |
| Carregamento | Toda leitura assíncrona tem indicador; nunca substituir o conteúdo por um espaço em branco |
| Lista vazia | Arrays vazios são válidos; a tela mostra mensagem orientativa |
| Erro | `{ code, message }`; a tela mostra mensagem próxima à ação e permite tentar de novo |

## 6. Decisões que o Prompt 02 deve manter

1. IDs estáveis e `workspaceId` como chave de vínculo — nunca a branch.
2. `sequence` gerado apenas no backend; usado para deduplicação e reconexão.
3. Semântica de pausa em duas fases (solicitada → confirmada).
4. Falha não avança o cursor; etapas restantes ficam pendentes.
5. Ações Git (commit, publicar, abrir PR) permanecem bloqueadas até a integração real.
6. Dados Git e execuções são identificados como demonstração na interface.

---

## 7. Status da implementação (Prompt 02)

O backend local implementa os fluxos persistentes com FastAPI + SQLite. Rotas relativas
efetivamente expostas:

```text
GET   /api/health
GET   /api/projects
POST  /api/projects
GET   /api/projects/{projectId}
PATCH /api/projects/{projectId}
GET   /api/projects/{projectId}/workspaces
POST  /api/projects/{projectId}/workspaces
GET   /api/workspaces/{workspaceId}
PATCH /api/workspaces/{workspaceId}
GET   /api/workspaces/{workspaceId}/state
GET   /api/workspaces/{workspaceId}/conversations
POST  /api/workspaces/{workspaceId}/conversations?title=...
POST  /api/workspaces/{workspaceId}/messages?conversationId=...
GET   /api/workspaces/{workspaceId}/batches
GET   /api/workspaces/{workspaceId}/attempts
GET   /api/workspaces/{workspaceId}/git
POST  /api/workspaces/{workspaceId}/plan/review
POST  /api/workspaces/{workspaceId}/queue?versionId=...
GET   /api/plans/{workspaceId}
PUT   /api/plans/{workspaceId}
GET   /api/plans/{workspaceId}/versions
POST  /api/batches?workspaceId=...
GET   /api/batches/{batchId}?workspaceId=...
POST  /api/batches/{batchId}/items?workspaceId=...
PATCH /api/batches/{batchId}/items/{itemId}?workspaceId=...
DELETE /api/batches/{batchId}/items/{itemId}?workspaceId=...
POST  /api/batches/{batchId}/items/reorder?workspaceId=...
```

Diferenças em relação ao contrato previsto no Prompt 01:

- `POST /api/batches` usa `?workspaceId=` em vez de corpo para o vínculo; o corpo opcional
  aceita `{ "name": "..." }`.
- Reordenação usa `POST /api/batches/{id}/items/reorder` com `{ "orderedIds": [...] }`.
  O backend exige o conjunto **exato** de IDs do lote e apenas itens `pending`.
- `PUT /api/plans/{workspaceId}` cria sempre uma **nova versão**; a versão anterior vira
  imutável e o lote gerado guarda `source_version_id`.
- Respostas de erro usam `{ "code", "message" }` com `code` em
  `VALIDATION | NOT_FOUND | INVALID_STATE | INVALID_ORDER | DUPLICATE_BRANCH | ...`.
- `GET /api/workspaces/{id}/attempts` devolve `[]` até o motor de fila existir.
- Rotas de execução (`start`, `pause`, `resume`, `cancel`) **não** estão expostas: o painel
  mantém os controles desabilitados no modo conectado.

O frontend alterna entre `MockAdapter` (demo) e `HttpAdapter` (conectado) pelo mesmo
contrato `ExtendedAdapter`. `HttpAdapter` usa token de atualização para descartar respostas
atrasadas de espaços trocados rapidamente.

---

## 8. Git local e worktrees (Prompt 03)

```text
POST /api/git/probe                              corpo: { "path": "..." }
POST /api/git/projects/{projectId}/repository    corpo: { "path": "..." }
GET  /api/git/projects/{projectId}/overview
POST /api/git/workspaces/{workspaceId}/branches  corpo: { "branch": "...", "startRef": "refs/heads/main" }
POST /api/git/workspaces/{workspaceId}/open      corpo: { "action": "link|attach|remote", "path"?,
                                                        "sourceRef"?, "branch"? }
GET  /api/git/workspaces/{workspaceId}/status
POST /api/git/workspaces/{workspaceId}/refresh
GET  /api/git/workspaces/{workspaceId}/diff?file=...&staged=...&untracked=...
POST /api/git/workspaces/{workspaceId}/verify
```

- Todos os caminhos são resolvidos no **backend**; o cliente nunca informa a raiz canônica.
- `probe` aceita subpastas e devolve `root`, `commonDir`, `isWorktree`, `state` e `refs`.
- `overview` devolve branches locais, referências remotas disponíveis localmente e sugestões
  de base (`main`, `master`) com o commit exato. Se local e remoto divergirem, ambas as opções
  vêm em `suggestions[].options`.
- `branches` cria a branch e a worktree em `OCILIMIT_WORKTREES_DIR`, verifica raiz/repositório
  comum/branch/HEAD e persiste o vínculo em uma transação.
- `open` com `action=link` vincula uma worktree já existente (sem duplicá-la); `attach` cria
  worktree para branch local livre; `remote` cria a branch local a partir da referência informada.
- Erros de recuperação usam `detail.worktreeCreated = true`, `detail.path` e `detail.branch`.
  O cliente reenvia `open` com `action=link`, `path` e `branch` para recuperar sem apagar arquivos.
- `status` usa `git status --porcelain=v1 -z` e `git worktree list --porcelain`. Cada arquivo
  traz `indexStatus`, `worktreeStatus`, `staged`, `unstaged`, `untracked`, `conflict`, `binary`,
  `path` e `oldPath` (renomeados). `operations` lista merge/rebase/cherry-pick em andamento.
- `diff` aceita somente arquivos relativos e dentro do espaço validado no servidor; devolve
  `available`, `text`, `binary`, `truncated` e `reason`. Binários e prévias truncadas são explícitos.
- `GET /api/workspaces/{id}/git` e `/state` passaram a incluir `head`, `repoRoot`, `gitStatus`,
  `linked`, `summary`, `files`, `operations` e `verification`. Espaços antigos vêm como `pending`.

### Operação reutilizável para o Prompt 04

`POST /api/git/workspaces/{workspaceId}/verify` (implementada em `app.git.service.verify`):

```json
{
  "workspaceId": "ws_...",
  "path": "C:/.../worktrees/feat-x",
  "branch": "feat/x",
  "observedBranch": "feat/x",
  "head": "abc123...",
  "boundHead": "abc123...",
  "originCommit": "def456...",
  "ready": true,
  "reasons": [],
  "localChanges": { "total": 2, "staged": 1, "unstaged": 1, "untracked": 0, "conflicts": 0 },
  "operations": []
}
```

Motivos possíveis em `reasons`: `MISSING_PATH`, `INVALID_REPOSITORY`, `WRONG_REPOSITORY`,
`BRANCH_CHANGED`, `DETACHED_HEAD`, `CONFLICTS`, `OPERATION_IN_PROGRESS`, `LINK_PENDING`.
O motor de fila deve chamar esta operação antes de iniciar cada prompt.

---

## 9. Motor da fila e OpenCode (Prompt 04)

```text
GET   /api/queue/opencode/status
GET   /api/queue/opencode/config
PUT   /api/queue/opencode/config        corpo: { executable?, model?, agent?, timeout? }
POST  /api/queue/opencode/test          diagnóstico explícito
GET   /api/queue/batches/{batchId}
POST  /api/queue/batches/{batchId}/start
POST  /api/queue/batches/{batchId}/pause
POST  /api/queue/batches/{batchId}/resume
POST  /api/queue/batches/{batchId}/cancel
POST  /api/queue/attempts/{attemptId}/retry   corpo: { "continueSession": false }
GET   /api/queue/attempts/{attemptId}/log?offset=0&limit=16000
GET   /api/queue/state?workspaceId=...
POST  /api/queue/recover
```

- A fila pertence ao backend: uma tarefa por lote, locks por `workspace_id` e verificação Git
  (`/api/git/.../verify`) antes de **cada** tentativa. O cliente envia prompts por argumento separado
  (UTF-8, sem shell); acima de 30.000 bytes a solicitação é rejeitada sem truncar.
- `opencode run --format json --standalone [--session id] [--model m] [--agent a] -- <prompt>`.
  Capacidades são lidas de `opencode run --help`. O cliente mantém o processo para cancelamento
  no Windows (`terminate()` → `kill()` se necessário) e confirma o término antes de liberar a worktree.
- Um evento estruturado de conclusão (`result`/`session.idle`/`step_finish` com status completado)
  **e** ausência de eventos de erro são necessários para `success`. Código de saída zero isolado
  resulta em `inconclusive` e bloqueia o avanço.
- Tentativa guarda `prompt_snapshot`, `session_id`, `requested_model`, `observed_model`,
  `head_before`/`head_after`, `git_status_before`/`after`, `exit_code`, `events`, `log_path` e `pid`.
- Log é lido por trechos com `offset`/`nextOffset`/`done`; o painel faz polling de `/api/queue/state`.
- Recuperação no startup marca tentativas `running` como `interrupted`; se o PID anterior parecer
  vivo, o lote fica com `block_reason = PREVIOUS_PROCESS_ALIVE`. Nunca há repetição automática.
- Eventos futuros devem carregar `batchId`, `attemptId`, `sequence` e `workspaceId` no `context`
  do envelope da seção 3 (integração remota no Prompt 07).

Serviço reutilizável para o Prompt 05: `app.opencode.client.OpenCodeClient` e o vínculo de sessão
`attempts.session_id` + `resume_of` via `retry` com `continueSession: true`.

---

## 10. Chat, análise e revisão (Prompt 05)

```text
GET  /api/assistant/chat/{workspaceId}/state
POST /api/assistant/chat/{workspaceId}/messages?conversationId=...   corpo: { "content": "..." }
POST /api/assistant/chat/{workspaceId}/new-session?conversationId=...
POST /api/assistant/analyze/{workspaceId}                            corpo: { "objective": "..." }
POST /api/assistant/plan/{workspaceId}/proposal                      corpo: { "analysisId", "answers" }
GET  /api/assistant/plan/{workspaceId}/proposal
POST /api/assistant/plan/{workspaceId}/approve                       corpo: { "proposalId", "objective"?, "steps"? }
POST /api/assistant/plan/{workspaceId}/batch                         corpo: { "versionId", "force"? }
POST /api/assistant/review/{workspaceId}?batchId=...
GET  /api/assistant/review/{workspaceId}
```

- A mensagem do usuário é gravada **antes** da chamada ao OpenCode. A resposta é atualizada em
  `messages.partial` enquanto chega; estados: `responding`, `completed`, `failed`, `interrupted`.
  Cada envio tem um `chat_attempt_id`; nova tentativa posterior vincula-se à mensagem original.
- Conversa mantém `session_id` de **planejamento**, distinto de `attempts.session_id` (execução).
  `new-session` cria outra conversa com `summary` do histórico e `sessionStatus = restarted`.
- Análise e geração de proposta aguardam a fila estabilizar e resolvem branch/pasta pelo ID do espaço.
  A resposta do OpenCode é tratada como proposta: JSON inválido, etapa incompleta, dependência ausente
  ou ciclo geram `plan_proposals.status = invalid` com `validationError` — **nenhum lote é criado**.
- `approve` revalida e chama `plans.save_plan_version`: nova versão imutável, `source_analysis_id`,
  `source_proposal_id` e `branch`. Edições em plano aprovado também criam nova versão.
- `batch` é idempotente por `source_version_id` (sem `force`); `force: true` cria explicitamente outro.
  Itens recebem `content` (prompt) e `acceptanceCriteria` copiados da versão aprovada.
- Revisão grava `reviews` com `batchId`, `versionId`, HEAD observado e `gitChangedSinceExecution`.
  Cada critério é `verified`, `pending` ou `insufficient_evidence`; afirmação do agente sem evidência
  não conta como teste confirmado. `suggestedSteps` viram etapas complementares via aprovação.

Eventos futuros devem continuar com `batchId`, `attemptId`, `sequence` e `workspaceId` no `context`.
Resumo para o Prompt 06: `docs/handoff/2026-11-21-prompt06-resumo.md`.

---

## 11. Entrega: commit, push e PR (Prompt 06)

```text
GET  /api/delivery/state?workspaceId=...
POST /api/delivery/preview
POST /api/delivery/commit
POST /api/delivery/push
POST /api/delivery/pr/preview
POST /api/delivery/pr
POST /api/delivery/pr/refresh
```

- Toda escrita revalida o vínculo Git pelo `workspace_id` e é bloqueada com `QUEUE_BUSY` se a fila
  estiver ativa. Leituras (state/status/diff/verify) permanecem disponíveis.
- `preview` devolve `previewId`, arquivos com estado preparado/não preparado, `selected`,
  `stagedOutsideSelection` e um digest de HEAD/índice. `commit` recalcula o digest: divergência gera
  `STALE_PREVIEW` com `detail.freshPreviewId`, exigindo nova revisão.
- Preparados fora da seleção geram `STAGED_OUTSIDE_SELECTION` e o índice é preservado. Falha de commit
  devolve `detail.staged` com o índice atual (`COMMIT_FAILED`). Caminhos são validados dentro da worktree.
- `push` usa `git push -u <remoto> <branch>` (sem force). Em timeout devolve `PUSH_UNCERTAIN` com o HEAD
  remoto observado; nunca repete sem consultar o remoto.
- PR: base sugerida é a do espaço; descrição separa verificações registradas de relatos e pendências.
  PR ativo para a mesma origem/destino é reaproveitado; `forceNew: true` cria explicitamente outro.
  Comunicação incerta gera `PR_UNCERTAIN` com o PR existente consultado.
- SQLite guarda apenas vínculos (espaço, lote, tentativa, repositório, número do PR e último estado).
  Git é a fonte dos commits; GitHub é a fonte do PR. Credenciais são mascaradas em erros/logs.

Ações de escrita a proteger no túnel: `docs/handoff/2026-11-21-prompt07-resumo.md`.

---

## 12. Acesso remoto, sessões e eventos (Prompt 07)

```text
GET  /api/remote/status
POST /api/remote/login                 corpo: { "password": "..." }
POST /api/remote/logout
GET  /api/remote/sessions
POST /api/remote/enable
POST /api/remote/disable
GET  /api/events?workspaceId=...&after=...
WS   /ws/events?workspaceId=...&after=...
```

- Remoto começa desativado. Com remoto ativo, toda rota `/api/...` (exceto status/login) exige cookie
  `ocilimit_session` válido (Hash SHA-256 no banco), não expirado e não revogado.
- Cookie: `HttpOnly`, `SameSite=Strict`, `Secure` quando a origem pública é HTTPS. Escritas exigem
  `X-CSRF-Token` igual ao CSRF da sessão. Logout e `disable` revogam sessões; `expiração` é verificada.
- Cabeçalho de identidade do túnel é apenas **sugestão de rótulo** — nunca prova de identidade sem
  validação no provedor.
- WebSocket valida `Origin` contra `OCILIMIT_ALLOWED_ORIGINS`/`OCILIMIT_PUBLIC_ORIGIN` (e origens locais)
  e exige sessão quando o remoto está ativo. A inscrição é por `workspaceId`; eventos de outras branches
  nunca são enviados.
- Todo evento tem `sequence` atribuído pelo backend, `context` com `workspaceId` e `type`. A resposta
  `GET /api/events` inclui `sequence`, `events` e `resync`. O `snapshot` inicial do WebSocket informa a
  sequência atual; lacunas (*resync*) exigem refetch do estado completo. Duplicatas (sequência menor ou
  igual à última recebida) são ignoradas pelo cliente.
- Escritas aceitam `Idempotency-Key`: repetições devolvem a resposta confirmada com
  `X-Idempotent-Replay: 1`. Auditoria registra horário, usuário, espaço, ação e status — sem credenciais.
- Operações locais bloqueadas no modo remoto: `/api/queue/opencode/config` (PUT),
  `/api/git/probe`, `POST /api/git/projects/{id}/repository`, `open` com `action=link`, e admin de sessões.
- O build do React é servido em `/` pelo mesmo backend quando `dist/` existe; localmente o Vite mantém
  o proxy `/api` e o WebSocket na mesma origem do navegador.

---

## 13. Descoberta automática de projetos (Prompt 08)

```text
POST /api/discovery/preview              corpo: { "path": "...", "github": true }
POST /api/discovery/open                 corpo: { "path": "...", "choices": { ... } }
GET  /api/discovery/preferences?projectId=...
PUT  /api/discovery/preferences          corpo: { "projectId", "baseBranch", "publishRemote", "prRepository", "prBase" }
GET  /api/discovery/worktrees?workspaceId=...
```

- `preview` é somente leitura: resolve a raiz da worktree (inclusive a partir de subpastas), identifica o
  repositório comum, lê branch/HEAD, worktrees, remotos, upstream efetivo e base padrão conhecida
  localmente. Preferências salvas têm prioridade; a origem de cada dado é devolvida em `sources`
  (`salvo`, `git`, `github`, `local`, `padrao`).
- Cada remoto aparece uma única vez em `remotes`: `git remote -v` emite uma linha de fetch e outra de
  push com o mesmo nome, que são deduplicadas. Assim, um único remoto não gera escolha de publicação.
- Publicação (`publishRemote`) e base do PR (`prBase`) são campos distintos. Com GitHub autenticado,
  um PR ativo inequívoco sugere a base. Sem GitHub, usa-se a referência local conhecida, marcada como
  possivelmente desatualizada; se a base continuar incerta, `ambiguities` pede a escolha e a fila pode
  ser preparada.
- `open` reaproveita projeto e espaço pelo repositório comum + pasta + branch; IDs e histórico são
  preservados. Só cria registros novos quando necessário. `choices` aplica as decisões do usuário e
  salva as preferências com `updatedBy = usuario`.
- Respostas tardias do GitHub devem ser associadas ao `projectId`/`workspaceId` corretos; o cliente
  descarta atualizações de inscrições anteriores ao trocar de espaço. A atualização periódica carrega
  os espaços de todos os projetos e preserva o espaço ativo, para que a fila continue ligada ao projeto
  aberto mesmo quando ele não é o primeiro da lista.
- Informar pastas do Windows é operação local: com remoto ativo, `/api/discovery/preview` e `/open`
  retornam `LOCAL_ONLY` (403).

