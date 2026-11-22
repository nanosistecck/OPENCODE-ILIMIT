# OPENCODE ILIMIT — Frontend + Backend local (Prompt 02)

Painel web com persistência SQLite para projetos, espaços, mensagens, planos versionados
e filas. O frontend mantém o modo demonstração do Prompt 01 e passa a ter um modo
**conectado** que usa a API local FastAPI.

## Iniciar no Windows

Terminal 1 — backend (loopback `127.0.0.1:8000`):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend (`http://localhost:5173`, com proxy `/api` → backend):

```powershell
npm install
npm run dev
```

> Se o PowerShell bloquear a ativação do venv: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
> O backend também pode ser iniciado sem venv com `python -m uvicorn ...` a partir de `backend/`.

## Onde ficam os dados

- Padrão: `%USERPROFILE%\.opencode-ilimit\data\opencode-ilimit.db` (fora das pastas dos projetos).
- Personalizar: variável `OCILIMIT_DATA_DIR` (aceita caminho absoluto).
- Host/porta: `OCILIMIT_HOST` (padrão `127.0.0.1`) e `OCILIMIT_PORT` (padrão `8000`).
- Migrações em `backend/app/db/0001_initial.sql`, aplicadas automaticamente no startup.
  Cada conexão SQLite habilita `PRAGMA foreign_keys = ON`.

## Verificações

```powershell
# backend (na pasta backend/)
python -m pytest              # 13 testes: migração, persistência, isolamento, fila, versões

# frontend (na raiz)
npm run typecheck
npm run build
npm test                      # 5 testes do adaptador de demonstração
```

## Modos de operação

- **Conectado** (padrão): dados persistidos, carregados via `/api`. Se a API falhar, aparece
  um aviso com **Tentar novamente** e **Usar demonstração** — os dados simulados só entram
  quando você escolhe o modo Demo.
- **Demo**: dados fictícios e execução simulada do Prompt 01, incluindo pausa em duas fases.

O botão de alternância fica na sidebar e no cabeçalho (acessível em 360 px). A preferência
é salva em `localStorage`.

## Rotas usadas pelo painel

`GET /api/health`
`GET|POST /api/projects` · `GET|PATCH /api/projects/{id}` · `GET|POST /api/projects/{id}/workspaces`
`GET|PATCH /api/workspaces/{id}` · `GET /api/workspaces/{id}/state` · `GET|POST /api/workspaces/{id}/conversations`
`POST /api/workspaces/{id}/messages?conversationId=...` · `GET /api/workspaces/{id}/batches`
`GET /api/workspaces/{id}/attempts` · `GET /api/workspaces/{id}/git` · `POST /api/workspaces/{id}/plan/review`
`POST /api/workspaces/{id}/queue[?versionId=...]`
`GET|PUT /api/plans/{workspaceId}` · `GET /api/plans/{workspaceId}/versions`
`POST /api/batches?workspaceId=...` · `GET /api/batches/{id}?workspaceId=...`
`POST /api/batches/{id}/items?workspaceId=...` · `PATCH|DELETE /api/batches/{id}/items/{itemId}?workspaceId=...`
`POST /api/batches/{id}/items/reorder?workspaceId=...`

Contrato detalhado: `docs/api-contract.md`.

## Estrutura

```
backend/app/
  config.py          diretório de dados, host/porta (env)
  main.py            FastAPI, CORS, lifespan, handlers
  db/                conexão, migrações SQL
  domain/            regras de projetos, planos, lotes e conversas (fora das rotas)
  api/               schemas Pydantic, serializers e rotas
src/
  data/              fixtures + MockAdapter + HttpAdapter + contrato
  state/             AppProvider (modo/tema/adaptador) e hooks
  components/        componentes comuns, chrome e banner de API
  features/          chat, plano, execução, git, histórico, cadastro
```

## Git local e worktrees (Prompt 03)

Fluxo no painel (modo conectado):

1. Cadastre projeto e espaço em **Cadastrar projeto e espaço**.
2. Na aba **Git**, informe o caminho do repositório (pode ser uma subpasta — o backend resolve a raiz
   e o repositório comum). **O caminho pertence ao computador que executa o backend**, inclusive no celular.
3. Confira bases locais/remotas com o commit exato de cada referência (quando `main` e `origin/main`
   divergem, as duas opções aparecem).
4. Informe a branch e a referência de partida e clique em **Criar branch e worktree**.
   A branch original da pasta permanece intacta.
5. Veja status (preparado, não preparado, novo, renomeado, conflito, binário), prévia/diff por arquivo
   e **Atualizar Git** para refletir mudanças externas.

Worktrees ficam em `%USERPROFILE%\.opencode-ilimit\data\worktrees` (configurável por
`OCILIMIT_WORKTREES_DIR`). O nome da pasta é derivado da branch com caracteres válidos no Windows.
O banco guarda raiz, repositório comum, pasta canônica, branch, base_ref, commit original e o HEAD
observado no vínculo. Espaços antigos migraram para `git_status = pending` e podem ser verificados/vinculados.

Se a worktree for criada e o SQLite falhar, o painel oferece **Vincular worktree existente** —
a pasta é reaproveitada, sem apagar arquivos nem criar outra worktree para a mesma branch.

Rotas Git: `POST /api/git/probe`, `POST /api/git/projects/{id}/repository`,
`GET /api/git/projects/{id}/overview`, `POST /api/git/workspaces/{id}/branches`,
`POST /api/git/workspaces/{id}/open`, `GET|POST /api/git/workspaces/{id}/status|refresh`,
`GET /api/git/workspaces/{id}/diff` e `POST /api/git/workspaces/{id}/verify`.

## Verificações executadas

- Backend: `python -m pytest` → **27 testes aprovados** (migrações 0001/0002/0003, persistência,
  isolamento, Git com repositórios descartáveis e motor da fila: sequência de 3 prompts, falha com
  terceiro pendente, retry com nova tentativa, bloqueio de execução duplicada, pausa em duas fases,
  cancelamento, recuperação sem repetir, simulador real e prompt longo rejeitado).
- Frontend: `npm run typecheck`, `npm run build` e `npm test` (5 testes) aprovados.
- Servidor real: OpenCode **v2.3.2 detectado**, capacidades lidas de `opencode run --help`
  (`--format json`, `--session`, `--model`, `--agent`, `--file` = sim); painel conectado e 360 px sem
  rolagem horizontal.

## Execução local (Prompt 04)

Variáveis de ambiente do backend:

- `OPENCODE_EXECUTABLE` — caminho do executável (padrão: auto-detecção no PATH/Windows).
- `OPENCODE_TIMEOUT` — timeout por tentativa em segundos (padrão `600`).
- Configuração adicional pelo painel: **Configuração do OpenCode** (executável, modelo, agente, timeout),
  com **Testar conexão** e **Enviar diagnóstico** (ação explícita).

Controles: **Executar lote**, **Pausar após esta etapa**, **Retomar**, **Cancelar**,
**Tentar novamente** e **Continuar sessão**. O painel consulta `/api/queue/state` a cada segundo e
lê o log por trechos (`offset`/`limit`). Fechar o navegador não interrompe a fila.

Estados do lote: `idle`, `running`, `pausing`, `paused`, `failed`, `cancelled`, `completed`,
`interrupted`. Estados da tentativa: `running`, `success`, `failure`, `cancelled`, `interrupted`,
`inconclusive`. Sucesso exige evento estruturado de conclusão **e** ausência de eventos de erro;
código de saída zero sozinho bloqueia o avanço.

## Limitações observadas

- O Git precisa estar no PATH do **backend**; o painel não instala/configura o Git.
- Caminhos longos no Windows e antivirus podem atrasar `git worktree add`.
- Prompts acima de 30.000 bytes são **rejeitados** (não truncados) para transporte seguro pela CLI.
- O executável real detectado está sem credencial válida: o diagnóstico retornou
  `provider.auth / 401 API key not valid`. Os fluxos de fila foram validados com simulador;
  a execução real depende de configurar o provedor no OpenCode/local.
- Interação solicitada pelo OpenCode não pode ser encaminhada por esta integração — o bloqueio aparece
  no log e as etapas seguintes ficam pendentes.
- Commit, push, PR, merge, WebSocket e túnel seguem para entregas futuras.

## Chat, planejamento e revisão (Prompt 05)

No modo conectado, a aba **Chat** reúne o fluxo completo:

1. Informe o objetivo e envie mensagens — cada mensagem é persistida **antes** de chamar o OpenCode.
   A resposta aparece como `Enviando` → `Respondendo` → `Concluído`; falhas preservam o texto, a resposta
   parcial e o erro, vinculados ao `chatAttemptId` da mensagem original.
2. **Analisar projeto** reúne objetivo, regras, branch, pasta e arquivos existentes, e pede ao OpenCode
   funcionalidades, lacunas, evidências, suposições e perguntas. A ação aguarda a fila estabilizar e
   **não** edita a worktree.
3. Responda às perguntas no campo **Respostas do usuário** e clique em **Gerar plano**. A proposta é
   validada no backend: etapas incompletas, dependências inválidas/cíclicas e JSON ausente ficam como
   `invalid`, com o erro visível — e **não** geram lote.
4. Revise títulos, prompts, aceite e dependências; **Aprovar versão** cria uma nova versão do plano.
   **Gerar lote** é idempotente por versão; **Novo lote da mesma versão** cria outro mediante pedido
   explícito. O lote nasce pendente e é iniciado na aba **Execução**.
5. **Revisar o que falta** compara critérios da versão executada com tentativas e estado Git atual.
   Cada critério aparece como **Verificado**, **Pendente** ou **Sem evidência suficiente**; mudanças de
   HEAD desde a execução são sinalizadas. Etapas complementares podem ser incorporadas à proposta.

A sessão de planejamento (`conversations.session_id`) é separada da sessão do lote
(`attempts.session_id`). Se a sessão deixar de existir, **Nova sessão** cria uma conversa com resumo.

Rotas: `GET /api/assistant/chat/{workspaceId}/state`, `POST .../messages`, `POST .../new-session`,
`POST /api/assistant/analyze/{workspaceId}`, `POST|GET /api/assistant/plan/{workspaceId}/proposal`,
`POST /api/assistant/plan/{workspaceId}/approve`, `POST /api/assistant/plan/{workspaceId}/batch`,
`POST|GET /api/assistant/review/{workspaceId}`.

### Verificações e limitações desta entrega

- Backend: **34 testes aprovados** (isolamento de chat entre branches, proposta válida/inválida/cíclica,
  resposta a pergunta e nova versão preservando o lote anterior, nova sessão com resumo, revisão apontando
  critério pendente). Frontend: build e 5 testes aprovados; layout em 360 px verificado.
- O adaptador CLI não consegue garantir modo somente-leitura; a limitação aparece no painel.
- O OpenCode real segue sem credencial válida (401); os fluxos foram validados com integração de teste.
- O resumo para o Prompt 06 fica em `docs/superpowers/specs/2026-11-21-opencode-ilimit-assistant-design.md`
  e `docs/handoff/2026-11-21-prompt06-resumo.md`.

## Commits, GitHub e PR (Prompt 06)

Na aba **Git**, o painel **Entrega da branch**:

1. Marque arquivos inteiros, veja os diffs preparado e do conteúdo atual, escreva a mensagem e clique em
   **Revisar seleção**. A prévia mostra branch, HEAD, arquivos que entram no commit e preparados fora da
   seleção — se houver conflito, resolva antes de confirmar.
2. **Criar commit local** prepara somente a seleção, confirma o novo hash no Git e registra o vínculo com
   lote/tentativa quando disponível. Se HEAD ou índice mudarem após a prévia, o backend exige nova revisão.
   Falha de identidade/hook preserva o índice e mostra o erro (credenciais mascaradas).
3. **Publicar** usa `git push -u <remoto> <branch>` — nunca force push. Commit local funciona sem `gh`.
4. **Preparar PR** sugere a base cadastrada (`main` por padrão), monta título/descrição com verificações e
   pendências distintas, e reaproveita PR ativo existente. **Abrir PR em rascunho** é a opção padrão;
   **Atualizar** consulta o estado remoto.

Migração `0005_delivery.sql`: `delivery_commits`, `delivery_pushes`, `delivery_pull_requests`.
Rotas: `GET /api/delivery/state`, `POST /api/delivery/preview`, `POST /api/delivery/commit`,
`POST /api/delivery/push`, `POST /api/delivery/pr/preview`, `POST /api/delivery/pr`,
`POST /api/delivery/pr/refresh`.

Verificações: backend **42 testes aprovados** (commit seletivo, índice preservado, prévia desatualizada,
fila bloqueando escrita, push com upstream em remoto de teste, PR rascunho/base diferente/reaproveitamento/
estado incerto e mascaramento de credenciais); build frontend e 5 testes aprovados.

Limitações: **`gh` não está instalado neste Windows** — PRs foram validados com integração de teste;
commit/push foram validados com Git real em repositório descartável. A mesclagem na base segue pelas regras
do GitHub. Ações de escrita a proteger no túnel estão em `docs/handoff/2026-11-21-prompt07-resumo.md`.

## Abrir projeto por descoberta (Prompt 08)

Clique em **Abrir projeto** (sidebar ou ícone no cabeçalho), informe a pasta do computador que executa
o backend e clique em **Detectar**. O painel mostra um resumo com projeto, branch de trabalho, pasta,
destino do PR e estado do OpenCode. Detalhes (upstream, remotos, worktrees, PR ativo e origem dos dados)
ficam sob demanda. Quando há ambiguidade, aparece apenas uma escolha curta (remoto de publicação,
base do plano, nome do projeto). **Ir para a fila** abre a fila do mesmo espaço.

Dados detectados: raiz da worktree (a partir de subpastas), repositório comum, branch e HEAD atuais,
worktrees existentes, remotos, upstream efetivo, base padrão conhecida localmente, PR ativo (quando o
GitHub está autenticado) e disponibilidade das ferramentas locais.

Preferências lembradas por projeto: base do plano, remoto de publicação, repositório do PR e base do PR.
A origem de cada valor aparece no painel (`salvo`, `git`, `github`, `local`, `padrao`). Preferência salva
sempre vence; se o GitHub estiver indisponível, a fila pode ser preparada e executada em uma worktree apta.

Rotas: `POST /api/discovery/preview`, `POST /api/discovery/open`, `GET|PUT /api/discovery/preferences`,
`GET /api/discovery/worktrees`. Informar caminhos é operação local (bloqueada no modo remoto).

Verificações: backend **56 testes** (8 novos de descoberta) aprovados em lotes (a suíte completa
excede 900 s neste ambiente), build e 5 testes do frontend aprovados. Smoke test no navegador com um
repositório Git real confirmou: detecção a partir de pasta, resumo sem escolha espúria para um único
remoto, e **Ir para a fila** abrindo a seção Execução com o espaço recém-criado ativo.

Correções encontradas no smoke test e já aplicadas: `git remote -v` devolve duas linhas por remoto
(fetch/push) e era lido como dois remotos — agora há deduplicação por nome, evitando escolha falsa e
chaves duplicadas no painel; a atualização periódica do frontend carregava apenas os espaços do
primeiro projeto e restaurava o espaço antigo — agora carrega os espaços de todos os projetos e
preserva o espaço ativo, mantendo a fila vinculada ao projeto aberto.

`gh` não está instalado neste Windows — PRs/base do PR foram testados com integração de teste; a branch
padrão do remoto pode estar desatualizada sem fetch (ação explícita).

## Contrato reaproveitado

- `workspace_id` é a chave de vínculo entre conversa, plano, fila e histórico; `branch` é exibição.
- `plan_versions.id` + `batches.source_version_id` mantêm a origem de cada lote.
- `batch_items` (`item_order`, `depends_on`, `acceptance_criteria`, `status`) é a base do motor.
- Envelope de eventos com `context`, `type` e `sequence` atribuído pelo backend (`docs/api-contract.md`).

## Acesso remoto (Prompt 07)

O acesso remoto fica **desativado por padrão**. O backend continua em loopback; o túnel do usuário deve
encaminhar somente a origem pública para a porta do backend, que serve o build do React (`dist/`) e a API
na mesma origem.

Configure no PC (variáveis de ambiente do backend):

```text
OCILIMIT_REMOTE_ENABLED=1
OCILIMIT_REMOTE_PASSWORD=<senha forte>
OCILIMIT_PUBLIC_ORIGIN=https://seu-endpoint.exemplo
OCILIMIT_ALLOWED_ORIGINS=https://seu-endpoint.exemplo
OCILIMIT_TUNNEL_PROVIDER=cloudflared
OCILIMIT_IDENTITY_HEADER=Cf-Access-Authenticated-User-Email
OCILIMIT_SESSION_HOURS=12
```

No celular, abra a URL pública, entre com a senha e use os controles normalmente. O painel mostra
**Tempo real conectado**, a sequência do último evento e o horário da última atualização; ao cair a rede,
preserva o último estado e bloqueia ações até reconectar. **Sair** revoga a sessão; o controle local
`POST /api/remote/disable` encerra todas as sessões sem parar a fila.

Rotas: `GET /api/remote/status`, `POST /api/remote/login`, `POST /api/remote/logout`,
`GET /api/remote/sessions`, `POST /api/remote/enable|disable`, `GET /api/events?workspaceId=&after=`,
`WS /ws/events?workspaceId=&after=`.

Ações locais mesmo com remoto ativo: configurar executável/credenciais, cadastrar caminhos do Windows e
administrar sessões. Commit/push/PR e controle da fila seguem exigindo confirmação explícita e revisão.
Detalhes em `docs/api-contract.md` (seção 12) e `docs/superpowers/specs/2026-11-21-opencode-ilimit-remote-design.md`.
