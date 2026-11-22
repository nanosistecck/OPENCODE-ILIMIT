# Design — Commits, GitHub e pull requests (Prompt 06)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Permitir entregar uma branch de trabalho pelo painel: revisar diff, selecionar arquivos, criar commit local,
publicar e abrir PR em rascunho — com cada escrita partindo de ação explícita e confirmada pelo backend.

## Objetivos

- Seleção de arquivos inteiros, com diffs preparado e não preparado.
- Prévia com HEAD/índice e detecção de mudanças externas antes do commit.
- Commit local seletivo, com vínculo a lote/tentativa e confirmação do hash.
- Push sem force, upstream configurado, recuperação de resultado incerto.
- PR em rascunho, base configurável, reaproveitamento de PR ativo e atualização de estado.
- Persistência dos vínculos e mascaramento de credenciais.

## Não-objetivos

- Acesso remoto/túnel, merge na base, push forçado, seleção de linhas dentro do arquivo.

## Anti-objetivos

- Alterar o índice sem revisão confirmada ou com a fila executando.
- Expor tokens/URLs com credenciais em erros do painel.
- Repetir push/PR após timeout sem consultar o estado remoto.

## Restrições

- Resolver pasta/branch/repositório no backend pelo ID do espaço.
- Git 2.56 disponível; GitHub CLI ausente neste Windows (adaptador de teste).
- Usar argumentos separados em subprocessos e limites de timeout.

## Abordagens consideradas

1. **Operar direto no frontend com Git local** — impossível no navegador/celular e sem validação central.
   Descartada.
2. **Biblioteca GitPython + API GitHub com token no app** — credenciais no aplicativo e dependência extra.
   Descartada.
3. **Git CLI + gh CLI no backend (escolhida)** — usa a autenticação local das ferramentas, mantém o
   backend como fonte da verdade e permite adaptador de teste para PR sem gh.

## Decisões

- Migração `0005_delivery.sql`: tabelas de commits, pushes e PRs com vínculos e último estado consultado.
- `preview` calcula digest de HEAD, índice, status, diffs e conteúdo de arquivos novos. Divergência exige
  nova prévia (`STALE_PREVIEW` + `freshPreviewId`).
- Preparados fora da seleção são conflito explícito; o índice nunca é limpo automaticamente.
- Commit usa `git add -- <paths>` + `git commit -m` (sem `-a`), confirma o novo HEAD e registra o hash.
- Push usa `git push -u <remoto> <branch>`; timeout/resultado incerto consulta `git ls-remote`.
- PR usa `gh pr list`/`gh pr create --draft`/`gh pr view`; base vem do espaço; descrição separa
  verificações registradas, relatos e pendências. Estado incerto consulta o GitHub antes de repetir.
- `sanitize()` mascara URLs com `user:pass@` e valores de token/password/secret/authorization.
- Escritas são bloqueadas com `QUEUE_BUSY` quando o motor está ativo; leituras continuam disponíveis.

## Verificação

42 testes de backend aprovados, incluindo 8 de entrega com repositório descartável e GitHub falso.
Build frontend e 5 testes aprovados. `gh` ausente: PRs validados por adaptador de teste.

## Handoff

Ações de escrita a proteger no túnel: `docs/handoff/2026-11-21-prompt07-resumo.md`.
