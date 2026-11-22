# Resumo para o Prompt 07 — túnel, acesso remoto e proteção de escrita

## Estado atual

- Backend local FastAPI + SQLite, escutando em `127.0.0.1:8000` por padrão.
- Painel React em `localhost:5173`, proxy `/api` para o backend.
- Worktrees em `%USERPROFILE%\.opencode-ilimit\data\worktrees`; banco no diretório de dados do app.
- Git 2.56 disponível; GitHub CLI (`gh`) **não** instalado neste Windows.

## Ações de escrita que o Prompt 07 DEVE proteger

Todas exigem ação explícita no painel e confirmação do backend. Com o túnel, exigir autenticação/autorização
e revalidar o vínculo do espaço no servidor antes de cada uma:

1. `POST /api/git/workspaces/{id}/branches` — cria branch e worktree.
2. `POST /api/git/workspaces/{id}/open` — vincula/abre worktree existente.
3. `POST /api/queue/batches/{id}/start|pause|resume|cancel` — executa/pausa/cancela OpenCode na worktree.
4. `POST /api/queue/attempts/{id}/retry` — repete tentativa (inclui `continueSession`).
5. `POST /api/delivery/preview` e `POST /api/delivery/commit` — alteram o índice Git e criam commit local.
6. `POST /api/delivery/push` — publica branch (nunca expor force push).
7. `POST /api/delivery/pr` e `POST /api/delivery/pr/refresh` — cria/atualiza PR no GitHub.

Leituras (`/state`, `/status`, `/diff`, `/verify`, logs, histórico) podem continuar disponíveis, mas devem
respeitar o mesmo isolamento por `workspace_id`.

## Regras já implementadas que o túnel precisa preservar

- Vínculo Git validado no backend pelo ID do espaço (`app.git.service.verify`) antes de qualquer escrita.
- Bloqueio de escrita enquanto a fila estiver ativa (`QUEUE_BUSY`).
- Uma execução ativa por workspace (locks do motor).
- Prévia com digest de HEAD/índice: mudança externa exige nova revisão (`STALE_PREVIEW`).
- Push sem `--force`; resultado incerto obriga consulta ao estado remoto antes de repetir.
- PR em rascunho por padrão; PR ativo existente é reaproveitado; falha de comunicação consulta o GitHub.
- Credenciais mascaradas em erros e logs (`app.delivery.gitops.sanitize`).
- Modo demonstração permanece explícito e separado do modo conectado.

## Verificações e pendências

- Backend: 42 testes aprovados; frontend: build e 5 testes aprovados.
- Git real validado em repositório descartável (commit seletivo, push com upstream, prévia desatualizada).
- PR validado com adaptador de teste — instalar/autenticar `gh` para validação real.
- OpenCode real sem credencial válida (401) — configurar provedor local.
- Pendente: auditoria/permissions no túnel, rate limiting, logs de auditoria por usuário e rotação de segredos.
