import { Bot, Send, User } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Collapsible, DemoNote, ErrorState, LoadingState, StatusBadge } from '../components/common';
import { useAdapter, useMode, useSnapshot } from '../state/AppContext';
import { ConnectedChatView } from './chatConnected';
import { useWorkspaceResource } from '../state/useWorkspaceResource';
import { formatTime } from '../utils/format';

export function ChatView() {
  const { mode } = useMode();
  return mode === 'connected' ? <ConnectedChatView /> : <DemoChatView />;
}

function DemoChatView() {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const { loading, error } = useWorkspaceResource();
  const { mode } = useMode();
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const conversation = snapshot.conversationsByWorkspace[snapshot.activeWorkspaceId];
  const disconnected = snapshot.connection !== 'connected';

  async function send() {
    if (!draft.trim() || !conversation || sending) return;
    setSending(true);
    setActionError(null);
    const text = draft;
    setDraft('');
    try {
      await adapter.sendMessage(snapshot.activeWorkspaceId, conversation.id, text);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Falha ao enviar');
      setDraft(text);
    } finally {
      setSending(false);
    }
  }

  if (loading) return <LoadingState label="Carregando conversa…" />;
  if (error) return <ErrorState message={error} />;
  if (!conversation) return <LoadingState label="Sem conversa para este espaço." />;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Chat</h1>
          <p>{conversation.title} · espaço {snapshot.activeWorkspaceId}</p>
        </div>
        <Badge tone={mode === 'demo' ? 'warning' : 'success'}>
          {mode === 'demo' ? 'Modo demonstração' : 'Persistido'}
        </Badge>
      </div>

      {mode === 'demo' ? (
        <DemoNote>
          Mensagens e atividade do agente são simuladas. Nenhuma requisição é enviada ao OpenCode nesta etapa.
        </DemoNote>
      ) : (
        <p className="panel-subtle">
          Mensagens são salvas no backend por espaço. Respostas do agente entram com a sessão real, em entrega futura.
        </p>
      )}

      {actionError && <ErrorState message={actionError} onRetry={() => setActionError(null)} />}

      <div className="view-grid">
        <section className="panel" aria-label="Mensagens">
          <div className="panel-header">
            <h2>Conversa</h2>
            <span className="panel-subtle">{conversation.messages.length} mensagem(ns)</span>
          </div>
          <div className="panel-body">
            {conversation.messages.length === 0 ? (
              <div className="empty-state">Nenhuma mensagem neste espaço.</div>
            ) : (
              <div className="chat-thread" role="log" aria-live="polite">
                {conversation.messages.map((message) => (
                  <article key={message.id} className="message">
                    <div className="message-avatar" aria-hidden="true">
                      {message.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div className="bubble">{message.content}</div>
                      <div className="message-meta">
                        <span>{message.role === 'user' ? 'Você' : 'OpenCode'}</span>
                        <span>{formatTime(message.createdAt)}</span>
                        <StatusBadge status={message.status} />
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}

            <div className="composer">
              <label className="sr-only" htmlFor="chat-draft">Mensagem</label>
              <textarea
                id="chat-draft"
                className="textarea"
                placeholder={disconnected ? 'PC desconectado — digite após reconectar' : 'Escreva uma mensagem…'}
                value={draft}
                disabled={disconnected || sending}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void send();
                  }
                }}
              />
              <Button variant="primary" onClick={() => void send()} disabled={!draft.trim() || disconnected || sending}>
                <Send size={14} aria-hidden="true" />
                {sending ? 'Enviando…' : 'Enviar'}
              </Button>
            </div>
            {mode === 'connected' && !disconnected && (
              <p className="panel-subtle" style={{ marginTop: 8 }}>
                Ao enviar, a mensagem é gravada com status "Salvo" no banco deste espaço.
              </p>
            )}
            {disconnected && (
              <p className="panel-subtle" style={{ marginTop: 8 }}>
                Último estado recebido preservado. O envio depende do PC.
              </p>
            )}
          </div>
        </section>

        <div className="stack">
          <Collapsible title="Atividade do agente" defaultOpen badge={<Badge tone="info">{conversation.activity.length}</Badge>}>
            <div className="activity-list">
              {conversation.activity.length === 0 ? (
                <p className="panel-subtle">Nenhuma atividade registrada.</p>
              ) : (
                conversation.activity.map((item) => (
                  <div key={item.id} className="activity-item">
                    <StatusBadge status={item.status} />
                    <div>
                      <div>{item.label}</div>
                      <span>{item.detail} · {formatTime(item.createdAt)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Collapsible>

          <section className="panel">
            <div className="panel-header"><h2>Sobre o espaço</h2></div>
            <div className="panel-body">
              <p className="panel-subtle">
                Este chat pertence ao espaço <span className="mono">{snapshot.activeWorkspaceId}</span>.
                Trocar de branch troca a conversa exibida.
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
