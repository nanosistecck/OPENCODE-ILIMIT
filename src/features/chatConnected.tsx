import {
  AlertTriangle, Bot, CheckCircle2, ClipboardList, FileSearch, Plus, RefreshCw, Send,
  ShieldCheck, Sparkles, User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import {
  Badge, Button, Collapsible, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { useAdapter, useSnapshot } from '../state/AppContext';
import type {
  Batch, ChatState, Plan, PlanProposal, ProjectAnalysis, ProposalStep, ReviewReport,
} from '../domain/types';
import { formatTime, shortId } from '../utils/format';

const STATUS_LABEL: Record<string, string> = {
  sending: 'Enviando', responding: 'Respondendo', completed: 'Concluído',
  interrupted: 'Interrompido', failed: 'Falhou', sent: 'Salvo',
};

export function ConnectedChatView() {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const workspaceId = snapshot.activeWorkspaceId;

  const [chat, setChat] = useState<ChatState | null>(null);
  const [analysis, setAnalysis] = useState<ProjectAnalysis | null>(null);
  const [proposal, setProposal] = useState<PlanProposal | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [review, setReview] = useState<ReviewReport | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [reviewBatch, setReviewBatch] = useState('');
  const [objective, setObjective] = useState('');
  const [answers, setAnswers] = useState('');
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const conversation = chat?.conversations[0];

  const refresh = useCallback(async () => {
    if (!workspaceId) { setLoaded(true); return; }
    try {
      const [nextChat, nextReview, nextBatches] = await Promise.all([
        adapter.getChatState(workspaceId),
        adapter.getReview(workspaceId),
        adapter.listBatches(workspaceId),
      ]);
      setChat(nextChat);
      setReview(nextReview);
      setBatches(nextBatches);
      setLoaded(true);
      if (!reviewBatch && nextBatches.length) setReviewBatch(nextBatches[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao carregar o chat.');
    }
  }, [adapter, workspaceId, reviewBatch]);

  useEffect(() => {
    setLoaded(false);
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 1200);
    return () => window.clearInterval(timer);
  }, [workspaceId]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na ação.');
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!draft.trim() || !conversation || busy) return;
    const text = draft;
    setDraft('');
    await run(() => adapter.sendChatMessage(workspaceId, conversation.id, text));
  }

  function updateStep(index: number, patch: Partial<ProposalStep>) {
    setProposal((current) => current ? {
      ...current,
      steps: current.steps.map((step, i) => (i === index ? { ...step, ...patch } : step)),
    } : current);
  }

  if (!loaded) return <LoadingState label="Carregando conversa…" />;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Chat e planejamento</h1>
          <p>Espaço {workspaceId} · sessão de planejamento separada da execução do lote.</p>
        </div>
        <div className="row">
          <Badge tone={conversation?.sessionId ? 'success' : 'neutral'}>
            {conversation?.sessionId ? `Sessão ${shortId(conversation.sessionId)}` : 'Sem sessão'}
          </Badge>
          {chat?.queueRunning && <Badge tone="warning">Fila em execução</Badge>}
        </div>
      </div>

      <p className="panel-subtle">
        <ShieldCheck size={13} aria-hidden="true" /> Análise e revisão usam permissões de leitura;
        o adaptador CLI não garante modo somente-leitura — confirme as permissões na instalação local.
        Consultas aguardam a fila estabilizar para refletir o estado atual da worktree.
      </p>

      {error && <ErrorState message={error} onRetry={() => { setError(null); void refresh(); }} />}

      <div className="view-grid">
        <div className="stack">
          <section className="panel">
            <div className="panel-header">
              <h2>{conversation?.title ?? 'Conversa'}</h2>
              <div className="row">
                <Badge tone="info">{conversation?.messages.length ?? 0} mensagem(ns)</Badge>
                {conversation && (
                  <Button small disabled={busy} onClick={() => void run(() => adapter.newChatSession(workspaceId, conversation.id))}>
                    <RefreshCw size={13} aria-hidden="true" /> Nova sessão
                  </Button>
                )}
              </div>
            </div>
            <div className="panel-body stack">
              {!conversation || conversation.messages.length === 0 ? (
                <EmptyState title="Conversa vazia" hint="Informe o objetivo para começar." />
              ) : (
                <div className="chat-thread" role="log" aria-live="polite">
                  {conversation.messages.map((message) => (
                    <article key={message.id} className="message">
                      <div className="message-avatar" aria-hidden="true">
                        {message.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div className="bubble">
                          {message.content || message.partial || 'Aguardando resposta…'}
                        </div>
                        <div className="message-meta">
                          <span>{STATUS_LABEL[message.status] ?? message.status}</span>
                          <span>{formatTime(message.createdAt)}</span>
                          {message.kind !== 'chat' && <span className="mono">{message.kind}</span>}
                        </div>
                        {message.error && <p className="panel-subtle">{message.error}</p>}
                      </div>
                    </article>
                  ))}
                </div>
              )}

              <div className="field">
                <label className="field-label" htmlFor="assistant-objective">Objetivo do espaço</label>
                <input
                  id="assistant-objective"
                  className="input"
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  placeholder="O que este espaço deve entregar?"
                />
              </div>
              <div className="composer">
                <label className="sr-only" htmlFor="assistant-draft">Mensagem</label>
                <textarea
                  id="assistant-draft"
                  className="textarea"
                  value={draft}
                  disabled={busy}
                  placeholder="Escreva para o OpenCode…"
                  onChange={(event) => setDraft(event.target.value)}
                />
                <Button variant="primary" disabled={busy || !draft.trim()} onClick={() => void send()}>
                  <Send size={14} aria-hidden="true" /> Enviar
                </Button>
              </div>
              {conversation?.sessionStatus === 'restarted' && (
                <p className="panel-subtle">Nova sessão iniciada com resumo do contexto anterior.</p>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Analisar projeto</h2>
              <FileSearch size={15} aria-hidden="true" />
            </div>
            <div className="panel-body stack">
              <Button
                variant="primary"
                disabled={busy || chat?.queueRunning}
                onClick={() => void run(async () => setAnalysis(await adapter.analyzeProject(workspaceId, objective)))}
              >
                <Sparkles size={14} aria-hidden="true" /> Analisar projeto
              </Button>
              {analysis && (
                <>
                  <StatusBadge status={analysis.valid ? 'success' : 'failure'} />
                  {analysis.error && <p className="panel-subtle">{analysis.error}</p>}
                  <pre className="console" tabIndex={0}>{analysis.content}</pre>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="field-label">Evidências</span>
                    {analysis.evidence.length === 0 ? <span className="panel-subtle">Nenhuma</span> : (
                      analysis.evidence.map((item) => <span key={item} className="mono panel-subtle">{item}</span>)
                    )}
                  </div>
                  <Collapsible title={`Perguntas e suposições (${analysis.questions.length + analysis.assumptions.length})`}>
                    {analysis.questions.map((item) => <p key={item} className="panel-subtle">? {item}</p>)}
                    {analysis.assumptions.map((item) => <p key={item} className="panel-subtle">→ {item}</p>)}
                  </Collapsible>
                  <div className="field">
                    <label className="field-label" htmlFor="assistant-answers">Respostas do usuário</label>
                    <textarea
                      id="assistant-answers"
                      className="textarea"
                      value={answers}
                      onChange={(event) => setAnswers(event.target.value)}
                      placeholder="Incorpore decisões à próxima proposta…"
                    />
                  </div>
                  <Button
                    disabled={busy || !analysis.id}
                    onClick={() => void run(async () => setProposal(await adapter.generateProposal(workspaceId, analysis.id, answers)))}
                  >
                    <ClipboardList size={14} aria-hidden="true" /> Gerar plano
                  </Button>
                </>
              )}
            </div>
          </section>
        </div>

        <div className="stack">
          {proposal && (
            <section className="panel">
              <div className="panel-header">
                <h2>Proposta de plano</h2>
                <Badge tone={proposal.status === 'invalid' ? 'danger' : 'info'}>{proposal.status}</Badge>
              </div>
              <div className="panel-body stack">
                <p className="objective">{proposal.objective || 'Sem objetivo'}</p>
                {proposal.scope && <KeyValue label="Escopo">{proposal.scope}</KeyValue>}
                {proposal.validationError && (
                  <div className="demo-banner error-banner" role="alert">
                    <AlertTriangle size={16} aria-hidden="true" />
                    <span>{proposal.validationError}</span>
                  </div>
                )}
                {proposal.questions.map((item) => <p key={item} className="panel-subtle">? {item}</p>)}
                <div className="field">
                  <label className="field-label" htmlFor="proposal-objective">Objetivo revisado</label>
                  <input
                    id="proposal-objective"
                    className="input"
                    value={proposal.objective}
                    onChange={(event) => setProposal({ ...proposal, objective: event.target.value })}
                  />
                </div>
                {proposal.steps.map((step, index) => (
                  <div key={step.id} className="step plan-editor-step">
                    <strong style={{ fontSize: '0.8rem' }}>Etapa {step.order}</strong>
                    <div className="field">
                      <label className="field-label" htmlFor={`step-title-${index}`}>Título</label>
                      <input
                        id={`step-title-${index}`}
                        className="input"
                        value={step.title}
                        onChange={(event) => updateStep(index, { title: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label className="field-label" htmlFor={`step-prompt-${index}`}>Prompt</label>
                      <textarea
                        id={`step-prompt-${index}`}
                        className="textarea"
                        value={step.prompt}
                        onChange={(event) => updateStep(index, { prompt: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label className="field-label" htmlFor={`step-accept-${index}`}>Critério de aceite</label>
                      <input
                        id={`step-accept-${index}`}
                        className="input"
                        value={step.acceptanceCriteria}
                        onChange={(event) => updateStep(index, { acceptanceCriteria: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label className="field-label" htmlFor={`step-deps-${index}`}>Dependências</label>
                      <input
                        id={`step-deps-${index}`}
                        className="input"
                        value={step.dependencies.join(', ')}
                        onChange={(event) => updateStep(index, {
                          dependencies: event.target.value.split(',').map((value) => value.trim()).filter(Boolean),
                        })}
                      />
                    </div>
                  </div>
                ))}
                <div className="row">
                  <Button
                    variant="primary"
                    disabled={busy || proposal.steps.length === 0}
                    onClick={() => void run(async () => {
                      setPlan(await adapter.approveProposal(workspaceId, proposal.id, {
                        objective: proposal.objective,
                        steps: proposal.steps.map((step, index) => ({
                          id: step.id,
                          order: index + 1,
                          title: step.title,
                          description: step.description ?? step.objective ?? '',
                          dependencies: step.dependencies,
                          acceptanceCriteria: step.acceptanceCriteria,
                          prompt: step.prompt,
                          status: 'pending' as const,
                        })),
                      }));
                    })}
                  >
                    <CheckCircle2 size={14} aria-hidden="true" /> Aprovar versão
                  </Button>
                  {plan && (
                    <Button
                      disabled={busy}
                      onClick={() => void run(async () => {
                        const version = plan.versions.find((item) => item.version === plan.version);
                        await adapter.createAssistantBatch(workspaceId, version?.id ?? String(plan.version));
                      })}
                    >
                      <Plus size={14} aria-hidden="true" /> Gerar lote
                    </Button>
                  )}
                  {plan && (
                    <Button
                      disabled={busy}
                      onClick={() => void run(async () => {
                        const version = plan.versions.find((item) => item.version === plan.version);
                        await adapter.createAssistantBatch(workspaceId, version?.id ?? String(plan.version), true);
                      })}
                    >
                      Novo lote da mesma versão
                    </Button>
                  )}
                </div>
              </div>
            </section>
          )}

          {plan && (
            <section className="panel">
              <div className="panel-header">
                <h2>Plano aprovado</h2>
                <Badge tone="success">v{plan.version}</Badge>
              </div>
              <div className="panel-body stack">
                <p className="objective">{plan.objective}</p>
                <KeyValue label="Branch"><span className="mono">{plan.steps.length} etapa(s)</span></KeyValue>
                {plan.steps.map((step) => (
                  <div key={step.id} className="history-item">
                    <strong>{step.order}. {step.title}</strong>
                    <small>{step.acceptanceCriteria}</small>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="panel">
            <div className="panel-header"><h2>Revisar o que falta</h2><ClipboardList size={15} aria-hidden="true" /></div>
            <div className="panel-body stack">
              <div className="field">
                <label className="field-label" htmlFor="review-batch">Lote executado</label>
                <select
                  id="review-batch"
                  className="select"
                  value={reviewBatch}
                  onChange={(event) => setReviewBatch(event.target.value)}
                >
                  {batches.map((batch) => (
                    <option key={batch.id} value={batch.id}>{batch.name} · {batch.status}</option>
                  ))}
                </select>
              </div>
              <Button
                disabled={busy || !reviewBatch || chat?.queueRunning}
                onClick={() => void run(async () => setReview(await adapter.buildReview(workspaceId, reviewBatch)))}
              >
                Revisar resultado
              </Button>
              {review && (
                <>
                  <div className="row">
                    <Badge tone={review.gitChangedSinceExecution ? 'warning' : 'success'}>
                      {review.gitChangedSinceExecution ? 'Git mudou desde a execução' : 'Git estável'}
                    </Badge>
                    <span className="panel-subtle">HEAD {shortId(review.head)}</span>
                  </div>
                  {review.criteria.map((criterion) => (
                    <div key={criterion.itemId} className="history-item">
                      <div className="spread">
                        <strong>{criterion.title}</strong>
                        <Badge tone={criterion.status === 'verified' ? 'success'
                          : criterion.status === 'pending' ? 'warning' : 'neutral'}>
                          {criterion.status === 'verified' ? 'Verificado'
                            : criterion.status === 'pending' ? 'Pendente' : 'Sem evidência suficiente'}
                        </Badge>
                      </div>
                      <small>{criterion.evidence}</small>
                    </div>
                  ))}
                  {review.suggestedSteps.length > 0 && (
                    <Collapsible title={`Etapas complementares (${review.suggestedSteps.length})`}>
                      {review.suggestedSteps.map((step) => (
                        <div key={step.id} className="step">
                          <strong style={{ fontSize: '0.8rem' }}>{step.title}</strong>
                          <p className="panel-subtle">{step.acceptanceCriteria}</p>
                          <Button small onClick={() => {
                            setProposal((current) => current ? {
                              ...current,
                              steps: [...current.steps, { ...step, order: current.steps.length + 1, dependencies: [] }],
                            } : current);
                          }}>
                            Incorporar à proposta
                          </Button>
                        </div>
                      ))}
                    </Collapsible>
                  )}
                  <p className="panel-subtle">
                    Relatório vinculado ao lote {shortId(review.batchId)} e à versão {shortId(review.planVersionId)}.
                  </p>
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
