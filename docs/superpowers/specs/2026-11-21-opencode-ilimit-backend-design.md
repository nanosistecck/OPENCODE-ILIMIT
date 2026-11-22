# Design — Backend local e persistência (Prompt 02)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Trocar os dados fictícios do Prompt 01 por persistência real em SQLite, mantendo o modo
demonstração como opção explícita e preservando todos os fluxos de navegação existentes.
O marco é salvar projeto, espaços, mensagens, plano e fila, reiniciar o backend e recuperar
cada espaço pelo seu ID.

## Objetivos

- FastAPI + SQLite com migrações reproduzíveis e `PRAGMA foreign_keys = ON` por conexão.
- Regras de projeto, plano e lote em módulos fora das rotas (reutilizáveis pelo motor de fila).
- Isolamento por `workspaceId` validado no servidor.
- Versionamento de plano com validação de dependências e lote vinculado à versão de origem.
- Frontend com `HttpAdapter` implementando o mesmo contrato do `MockAdapter`.

## Não-objetivos

- Git/worktrees reais, execução do OpenCode, respostas do agente, PR no GitHub,
  WebSocket e túnel de acesso remoto.

## Anti-objetivos

- Uma falha da API ser exibida como "modo demonstração" sem escolha do usuário.
- Misturar mensagens de branches diferentes.
- Reordenar itens sem validar o conjunto exato de IDs do lote.

## Restrições

- Dados em `%USERPROFILE%\.opencode-ilimit\data` (fora das pastas dos projetos),
  sobrescrito por `OCILIMIT_DATA_DIR`.
- Loopback por padrão (`127.0.0.1:8000`); proxy Vite `/api`.
- Horários em UTC; IDs estáveis; branch é exibição, ID é vínculo.
- Caminhos relativos na API; WebSocket real fica para entrega futura.

## Abordagens consideradas

1. **SQL direto nas rotas** — rápido, mas as regras ficariam inacessíveis ao futuro motor
   de execução e a validação de vínculos se repetiria. Descartada.
2. **ORM (SQLAlchemy/Alembic)** — robusto, porém dependências e cerimônia desproporcionais
   a um banco pequeno e local. Descartada.
3. **sqlite3 + módulos `domain/` + schemas Pydantic (escolhida)** — dependências mínimas,
   transações explícitas com `with conn`, regras reutilizáveis e contrato alinhado ao TS.

## Decisões

- `ConnectionState`/`apiStatus` passaram a fazer parte do snapshot; o `AppProvider` troca
  de adaptador conforme o modo salvo em `localStorage`.
- `HttpAdapter` usa `refreshToken` para descartar respostas atrasadas de trocas rápidas
  de espaço.
- Reordenação: `orderedIds` completo, conjunto exatamente igual ao do lote, itens `pending`;
  escrita em uma transação com ordens temporárias negativas para evitar colisão UNIQUE.
- Plano: `plan_versions` imutável; `batches.source_version_id` e cópia dos prompts na
  criação da fila; validação de dependências (mesma versão, ordem, sem ciclos).
- Controles de execução desabilitados no modo conectado com texto "Motor pendente".

## O que fica para o Prompt 03

Motor de fila com tentativas/sessões/eventos persistidos, WebSocket com `sequence` do
backend, verificação real de worktrees a partir de `work_dir`/`branch`, e execução do OpenCode.
