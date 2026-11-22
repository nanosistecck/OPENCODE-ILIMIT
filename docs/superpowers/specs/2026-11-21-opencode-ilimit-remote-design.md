# Design — Acesso remoto, autenticação e reconexão (Prompt 07)

**Data:** 2026-11-21
**Status:** implementado

## Intenção

Permitir que o mesmo backend atenda ao PC e a um celular via túnel, com autenticação, eventos em tempo real
e reconexão segura — sem duplicar serviços nem expor ferramentas internas.

## Objetivos

- Mesma origem pública para build React, API e WebSocket.
- Remoto desativado por padrão; kill switch local.
- Sessão com cookie seguro, CSRF, expiração e revogação.
- Eventos com sequência do backend, replay e resync em lacunas.
- Idempotência e auditoria das ações de escrita.
- Ações de configuração local bloqueadas no modo remoto.

## Não-objetivos

- Configurar/criar o túnel (já instalado pelo usuário) e validar identidade do provedor.
- Mover SQLite, OpenCode ou servidor de dev para fora do PC.

## Anti-objetivos

- Confiar em cabeçalho de identidade do túnel como prova.
- Repetir efeito de escrita quando a resposta HTTP se perder.
- Misturar eventos de outra branch na inscrição atual.

## Decisões

- Migração `0006_remote.sql`: sessões, `app_events`, `remote_operations` e `remote_audit`.
- Login por senha local configurada, cookie HttpOnly/SameSite=Strict/Secure em HTTPS, CSRF nas escritas.
- `GET /api/events` e `WS /ws/events` usam `after` como cursor; `resync` força refetch do estado completo.
- Eventos são publicados pelo middleware somente após resposta 2xx, com `workspaceId` resolvido no servidor.
- `Idempotency-Key` armazena a resposta confirmada; repetição devolve `X-Idempotent-Replay: 1`.
- Origens do WebSocket validadas; inscrição por `workspaceId`; sequências antigas descartadas no cliente.
- Frontend preserva o último snapshot na desconexão e aplica `remote-offline` para bloquear botões até sincronizar.
- Comandos de configuração e caminhos do Windows são locais; fila, chat, Git (por ID) e entrega permanecem
  disponíveis com confirmação explícita.

## Verificação

6 testes de backend cobrindo: remoto desativado, login/cookie/CSRF/logout, revogação, sequência e isolamento
de eventos, idempotência e WebSocket com snapshot + evento. Build frontend e testes do modo demo aprovados.
O túnel real e a validação de identidade do provedor dependem da configuração do usuário.
