# OPENCODE ILIMIT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o frontend de demonstração com contrato tipado, cinco áreas funcionais e simulação de execução, pronto para receber o backend no Prompt 02.

**Architecture:** Adaptador tipado (`Adapter`) como única porta de dados, implementado por `MockAdapter` com snapshot imutável notificado via `useSyncExternalStore`. Telas consomem somente o adaptador; fixtures ficam isolados. Autômato de execução com cursor e eventos sequenciados.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, lucide-react, CSS custom properties.

**Spec:** `docs/superpowers/specs/2026-11-21-opencode-ilimit-frontend-design.md`

## Global Constraints

- React + TypeScript + Vite; sem router; dependências proporcionais.
- Caminhos relativos para a futura API; WebSocket real fica para o Prompt 02.
- IDs estáveis para projeto/espaço/lote/tentativa; `workspaceId` é a chave de vínculo; `branch` é exibição.
- Telas não importam `fixtures.ts`.
- 360 px sem rolagem horizontal; foco visível; `prefers-reduced-motion`.
- Rótulos de estado sempre acompanhados de texto; execuções e Git identificados como simulação.

## Review Focus

1. Troca de espaço — cada view deve usar `activeWorkspaceId`; teste: isolamento entre `ws-canvas` e `ws-apis`.
2. Pausa em duas fases — `pausing` ≠ `paused`; teste: status após `requestPause` e após a etapa.
3. Falha na 2ª etapa — terceira permanece `pending`; teste: estados dos itens após `failed`.
4. Desconexão — último estado preservado e ações bloqueadas; teste: `AdapterError` com `DISCONNECTED`.
5. Contrato tipado — nenhuma tela importa dados de exemplo; verificação por inspeção de imports.

---

### Task 1: Fundação e contrato de domínio ✅

**Files:**
- Create: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.gitignore`
- Create: `src/domain/types.ts`, `src/domain/navigation.ts`
- Create: `src/data/adapter.ts`, `src/data/fixtures.ts`

- [x] Definir tipos de projeto, espaço, conversa, mensagem, plano, versão, etapa, lote, item, tentativa, verificação e evento.
- [x] Definir `Adapter` com listagem, estado do espaço, envio de mensagem, fila e ações de execução.
- [x] Criar fixtures da NIA (base `main` + 2 worktrees) isolados em `fixtures.ts`.
- [x] Verificar: `npm install` e `npm run typecheck`.

### Task 2: MockAdapter e simulação ✅

**Files:**
- Create: `src/data/mockAdapter.ts`, `src/data/mockAdapter.test.ts`

- [x] Implementar snapshot imutável, `subscribe`/`getSnapshot` e eventos com `sequence`.
- [x] Implementar autômato: iniciar, pausar (solicitada/confirmada), retomar, cancelar.
- [x] Garantir falha na etapa 2 do lote de exemplo sem avançar o cursor.
- [x] Testar falha, pausa, retomada, isolamento de espaços e desconexão: `npm test` (5 aprovados).

### Task 3: Estado global e sistema visual ✅

**Files:**
- Create: `src/state/AppContext.tsx`, `src/state/useWorkspaceResource.ts`, `src/styles.css`

- [x] `AppProvider` com `MockAdapter`, `useSnapshot` via `useSyncExternalStore` e tema persistido.
- [x] Tokens CSS para dark/light, glassmorphism, responsividade 360 px, foco e movimento reduzido.
- [x] Hook de carregamento/erro do contrato.

### Task 4: Componentes comuns e navegação ✅

**Files:**
- Create: `src/components/common.tsx`, `src/components/layout.tsx`, `src/App.tsx`, `src/main.tsx`

- [x] `Badge`/`StatusBadge`, `Button`, `Collapsible`, `DemoNote`, estados vazio/erro/carregamento.
- [x] Sidebar de projetos/espaços, cabeçalho com branch/conexão, nav móvel, inspetor recolhível.
- [x] Alternância de tema e simulação de queda de conexão.

### Task 5: Telas funcionais ✅

**Files:**
- Create: `src/features/chat.tsx`, `plan.tsx`, `execution.tsx`, `git.tsx`, `history.tsx`

- [x] Chat com envio simulado e atividade recolhível.
- [x] Plano com etapas, revisão e geração de fila.
- [x] Execução com prompts/arquivos, reordenação, controles e saída.
- [x] Git demonstrativo e histórico com vínculo por ID.

### Task 6: Documentação e verificação final ✅

**Files:**
- Create: `docs/api-contract.md`, `README.md`, design doc e este plano.

- [x] Registrar endpoints relativos, envelope de eventos, `sequence` do backend e WebSocket reservado.
- [x] Registrar decisões que o Prompt 02 deve manter.
- [x] Verificar: `npm run typecheck`, `npm run build`, `npm test`.
