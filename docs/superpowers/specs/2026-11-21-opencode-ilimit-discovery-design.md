# Design — Descoberta automática de projetos Git (Prompt 08)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Reduzir a entrada de projetos a: informar uma pasta, conferir um resumo e ir para a fila. Toda a
configuração identificável é descoberta pelo backend; o usuário só escolhe quando há ambiguidade.

## Objetivos

- Resolver raiz da worktree a partir de subpastas e reconhecer worktrees do mesmo repositório.
- Distinguir branch atual, upstream e base do PR.
- Separar destino de publicação e repositório/base do PR (forks).
- Reaproveitar preferências salvas e IDs existentes.
- Permitir preparar a fila sem GitHub autenticado.
- Manter a descoberta como leitura; escritas continuam explícitas nos fluxos anteriores.

## Não-objetivos

- Empacotamento/executável, criação de worktree, fetch, commit, push e abertura de PR automáticos.

## Decisões

- Migração `0007_discovery.sql`: `project_discovery_preferences` e `workspace_discovery`.
- Identidade do projeto pelo repositório comum (`git_common_dir`), não pelo nome.
- Preferência salva > PR ativo confirmado > referência padrão local > `main`.
- `sources` indica a origem de cada dado, exibida no painel.
- `ambiguities` contém apenas escolhas curtas (remoto, base, nome), nunca um formulário completo.
- `open` reaproveita espaço por `(project_id, git_work_dir, git_branch)` e preserva conversas/lotes.
- Respostas do GitHub são associadas ao projeto/espaço da consulta; o cliente descarta eventos de
  inscrições anteriores ao trocar de branch.
- Caminhos do Windows permanecem operação local (remoto ativo retorna `LOCAL_ONLY`).

## Verificação

56 testes de backend aprovados em lotes (8 de descoberta: subpasta e reabertura, duas worktrees, fork
com bases distintas, preferência salva, GitHub indisponível, base sem worktree pronta, bloqueio remoto e
um único remoto sem ambiguidade). Build e 5 testes do frontend aprovados. Smoke test com repositório Git
real validou detecção e **Ir para a fila** até a seção Execução com o espaço correto ativo; revelou e
corrigiu a duplicação de remotos em `git remote -v` e a perda do espaço ativo pela atualização periódica
que lia só o primeiro projeto.

## Limitações

`gh` não está instalado neste Windows: PRs e base do PR foram validados com adaptador de teste.
A branch padrão de um remoto pode estar desatualizada sem fetch, que continua sendo ação explícita.
