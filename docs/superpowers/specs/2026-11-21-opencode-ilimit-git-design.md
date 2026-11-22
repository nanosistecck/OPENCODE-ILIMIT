# Design — Git local e espaços por branch (Prompt 03)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Fazer de cada espaço de trabalho um vínculo verificável com um repositório Git real, uma branch
e uma worktree própria, mantendo os dados dos Prompts 01 e 02 e o modo demonstração intactos.
O painel passa a mostrar status/diff reais e expõe uma verificação reutilizável para o motor de fila.

## Objetivos

- Resolver subpastas para a raiz e identificar o repositório comum às worktrees.
- Mostrar branches locais/remotas locais, base sugerida e commit exato de cada referência.
- Criar branch em worktree nova; abrir worktree existente; criar worktree para branch local;
  criar branch local a partir de referência remota.
- Status e diff reais por espaço, com estados para novo, binário, conflito e truncamento.
- Operação `verify` reutilizável com motivos específicos.

## Não-objetivos

- Commit, staged selection, push, PR, merge, execução do OpenCode, WebSocket e túnel.

## Anti-objetivos

- Apagar worktree preexistente em caso de falha do SQLite.
- Aceitar caminhos de arquivo fora do espaço ou branch divergente sem aviso.
- Transformar falha da API em "modo demo" automático.

## Restrições

- Git no PATH do **backend**; subprocess com lista de argumentos, timeout e UTF-8 tolerante.
- Worktrees em `OCILIMIT_WORKTREES_DIR` (padrão: diretório de dados do app).
- IDs e vínculos existentes preservados; horários UTC; nomes de pasta válidos no Windows.
- Caminhos relativos na API; loopback por padrão.

## Abordagens consideradas

1. **Chamar git diretamente nas rotas** — repetiria validação e impossibilitaria reuso pelo motor.
   Descartada.
2. **Biblioteca GitPython** — dependência extra e parsing opaco; preferimos saída *porcelain*
   estável do próprio Git. Descartada.
3. **`app/git/runner.py` + `local.py` + `service.py` (escolhida)** — subprocess centralizado,
   consultas puras e serviço com transações/locks; o mesmo serviço é usado pelas rotas e pelo Prompt 04.

## Decisões

- Migração `0002_git.sql` usa `ALTER TABLE ... ADD COLUMN` com `git_status DEFAULT 'pending'`;
  registros antigos migram sem conversão manual.
- `origin_commit` (commit de partida) é distinto de `bound_head` (HEAD observado no vínculo).
- Locks em memória por `(branch, pasta)` evitam criações concorrentes duplicadas.
- Se a worktree é criada mas o banco falha, a exceção carrega `detail.worktreeCreated/path/branch`;
  o cliente recupera com `open(action=link, ...)`. Nada é apagado.
- `git status --porcelain=v1 -z` lida com espaços, acentos e renomeios; `git worktree list --porcelain`
  identifica a pasta da branch.
- Diff é limitado por `OCILIMIT_MAX_DIFF_CHARS`; binários são detectados por `--numstat`.
- `verify` roda no servidor e devolve `ready`, `reasons`, `head`, `boundHead`, `originCommit`
  e `localChanges` — é a operação que o Prompt 04 chamará.

## O que fica para o Prompt 04

Motor de fila com tentativas/eventos persistidos, uso de `verify` antes de cada prompt, decisão
sobre registrar mudanças locais, e transporte WebSocket; commit/push/PR seguem em entregas futuras.
