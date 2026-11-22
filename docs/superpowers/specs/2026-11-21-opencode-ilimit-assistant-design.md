# Design — Chat, planejamento e revisão (Prompt 05)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Fechar o ciclo objetivo → análise → plano aprovado → lote → execução → revisão, com persistência e
sessões separadas, mantendo o modo demo e a navegação por branch intactos.

## Objetivos

- Chat por espaço com mensagem persistida antes da chamada, resposta parcial e retry vinculado.
- Análise do projeto existente (evidências, lacunas, perguntas) sem editar a worktree.
- Proposta estruturada validada no backend; inválida nunca gera lote.
- Aprovação cria versão imutável; geração de lote idempotente por versão.
- Revisão de critérios com estados explícitos e etapas complementares.

## Não-objetivos

- Publicação/túnel, eventos remotos, commit/push/PR.

## Anti-objetivos

- Transformar afirmação do agente em evidência confirmada.
- Gerar lote a partir de proposta inválida ou duplicar lote por clique repetido.
- Misturar sessão de planejamento com sessão de execução.

## Restrições

- Reutilizar `OpenCodeClient`, `git.service.verify`, regras de plano do Prompt 02 e motor do Prompt 04.
- Pasta/branch resolvidas no backend pelo `workspace_id`.
- Modo somente-leitura desejado, mas não garantido pela CLI — limitação exibida no painel.

## Abordagens consideradas

1. **Gerar plano diretamente no frontend** — sem validação central e sem vínculo com versões/lotes.
   Descartada.
2. **Parser de linguagem natural sem validação** — propostas incompletas virariam lotes quebrados.
   Descartada.
3. **Proposta JSON validada no backend (escolhida)** — reuso das regras de dependências, rastreabilidade
   da origem e erro visível para revisão.

## Decisões

- Migração `0004_assistant.sql`: colunas de sessão/resposta, tabelas `analyses`, `plan_proposals`, `reviews`.
- `messages.kind` distingue `chat`, `analysis`, `proposal`, `system`; `role` permanece `user|assistant`
  por restrição CHECK legada.
- Dependências aceitam índices 1-based ou IDs `step-N` e são normalizadas antes de `validate_steps`.
- `approve` sempre cria nova versão via `plans.save_plan_version`; edição de plano aprovado segue o mesmo caminho.
- `batch` usa `source_version_id` como chave de idempotência; `force` é ação explícita.
- Revisão diferencia `verified` (resultado registrado), `pending` e `insufficient_evidence`; HEAD atual
  é comparado com o HEAD da primeira tentativa.
- Chat e fila são coordenados por `_wait_stable`: análise/revisão esperam a fila terminar.

## Verificação

34 testes de backend aprovados (7 novos de assistente), build frontend e 5 testes aprovados.
OpenCode real detectado, sem credencial válida (401); fluxos validados com integração de teste.

## Handoff

Resumo, verificados e pendências em `docs/handoff/2026-11-21-prompt06-resumo.md`.
