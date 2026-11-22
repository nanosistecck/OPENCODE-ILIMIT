# Design — OPENCODE ILIMIT, frontend responsivo e contrato inicial

**Data:** 2026-11-21
**Status:** aprovado e implementado (Prompt 01)

## Intenção

Entregar um painel web executável, com dados fictícios, que permita validar no Windows
e no celular a gestão de projetos, worktrees por branch, chats, planos, lotes e histórico
do OpenCode — sem depender do backend ainda, mas com um contrato tipado que o backend
Python/FastAPI + SQLite possa implementar depois sem alterar as telas.

## Objetivos

- Navegação por projeto/espaço com contexto isolado por `workspaceId`.
- Cinco áreas funcionais: Chat, Plano, Execução, Git e Histórico.
- Adaptador tipado como única porta de entrada de dados; fixtures isolados.
- Simulação de execução com estados distintos para pausa solicitada e confirmada.
- Interface acessível, responsiva a 360 px, com temas claro/escuro salvos.

## Não-objetivos

- Backend, persistência SQLite, chamadas HTTP reais ou WebSocket.
- Ações Git reais (commit, publicar, abrir PR).
- Autenticação, multiusuário, roteamento URL profundo.

## Anti-objetivos (o que tornaria a entrega um fracasso)

- Telas importando dados de exemplo diretamente.
- Misturar dados das duas branches ao trocar de espaço.
- Usar a branch como chave de vínculo no lugar do ID.
- Esconder o fato de que execuções e Git são simulados.

## Restrições

- React + TypeScript + Vite; dependências proporcionais (lucide-react para ícones).
- Caminhos relativos para a futura API; WebSocket real fica no Prompt 02.
- `sequence` de eventos é atribuído pelo backend, nunca pelo cliente.
- 360 px sem rolagem horizontal; foco visível; movimento reduzido respeitado.

## Abordagens consideradas

1. **Estado local por tela + mocks espalhados** — mais rápido, mas acopla as telas aos
   dados de exemplo e impossibilita a troca limpa por HTTP no Prompt 02. Descartada.
2. **Gerenciador de estado externo (Redux/Zustand) + serviços REST** — robusto, mas
   dependências e cerimônia desproporcionais a uma entrega de demonstração. Descartada.
3. **Adaptador tipado + `useSyncExternalStore` (escolhida)** — o adaptador é a única
   fonte de dados, notifica mudanças e expõe um snapshot imutável. O React acompanha o
   snapshot sem bibliotecas extras; trocar `MockAdapter` pela implementação real é uma
   substituição de uma linha no `AppProvider`.

## Decisões de implementação (minhas, registradas)

- **Navegação:** estado local em `App` (5 views), sem router. Justificativa: não há URLs
  profundas nesta etapa; reduz dependências.
- **Eventos:** cada mutação do adaptador gera um evento com `sequence` local apenas para
  visualização; o contrato deixa claro que no backend a sequência é sua.
- **Execução:** autômato com cursor e timers. `pausing` = solicitação pendente;
  `paused` = confirmação após a etapa. Falha não avança o cursor, mantendo as etapas
  seguintes `pending`.
- **Tema:** `data-theme` no `<html>`, tokens CSS redefinidos sob `[data-theme='light']`;
  preferência salva em `localStorage` com fallback para `prefers-color-scheme`.
- **Estilo (ui-ux-pro-max + glassmorphism):** dark tech, blur 10–22 px na navegação,
  borda 1 px translúcida, acento ciano — ícones SVG (lucide), nunca emoji;
  alvos de toque ≥ 44 px em ponteiro fino; sem movimento não essencial com
  `prefers-reduced-motion`.
- **Tipografia (frontend-design):** Plus Jakarta Sans para interface e JetBrains Mono
  para logs/diffs/IDs — contraste alto e hierarquia clara em conteúdo técnico.

## O que fica para o construtor

Nada nesta etapa: o Prompt 02 implementa o `Adapter` real e o transporte WebSocket,
mantendo as decisões acima e o contrato em `docs/api-contract.md`.
