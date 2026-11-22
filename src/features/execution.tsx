import {
  ArrowDown, ArrowUp, CheckSquare, FileText, Pause, Pencil, Play, Plus, RotateCcw, Square, Trash2,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';
import {
  Badge, Button, DemoNote, EmptyState, ErrorState, LoadingState, StatusBadge,
} from '../components/common';
import { useAdapter, useMode, useSnapshot } from '../state/AppContext';
import { ConnectedExecutionView } from './executionConnected';
import { useWorkspaceResource } from '../state/useWorkspaceResource';
import type { ViewId } from '../domain/navigation';
import { formatTime, shortId } from '../utils/format';

// Reexport aliases locais para manter a chamada legível.
const IconButton = ({ label, disabled, onClick, children }: {
  label: string; disabled?: boolean; onClick: () => void; children: ReactNode;
}) => (
  <button type="button" className="icon-btn" aria-label={label} title={label} disabled={disabled} onClick={onClick}>
    {children}
  </button>
);

export function ExecutionView({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const { mode } = useMode();
  return mode === 'connected'
    ? <ConnectedExecutionView />
    : <DemoExecutionView onNavigate={onNavigate} />;
}

function DemoExecutionView({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const { loading, error } = useWorkspaceResource();
  const { mode } = useMode();
  const isDemo = mode === 'demo';

  const [promptDraft, setPromptDraft] = useState('');
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const workspaceId = snapshot.activeWorkspaceId;
  const batches = snapshot.batchesByWorkspace[workspaceId] ?? [];
  const batch = batches.find((item) => item.id === selectedBatchId) ?? batches[0] ?? null;
  const attempts = snapshot.attemptsByWorkspace[workspaceId] ?? [];
  const batchAttempts = batch ? attempts.filter((attempt) => attempt.batchId === batch.id) : [];
  const currentAttempt = batchAttempts.find((attempt) => attempt.status === 'running') ?? batchAttempts[0] ?? null;
  const disconnected = isDemo
    ? snapshot.connection !== 'connected'
    : snapshot.apiStatus !== 'ok' || snapshot.connection === 'error';
  const locked = disconnected || busy || batch?.status === 'running' || batch?.status === 'pausing';
  const engineUnavailable = !isDemo;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Falha na ação');
    } finally {
      setBusy(false);
    }
  }

  async function addPrompt() {
    if (!batch || !promptDraft.trim()) return;
    const content = promptDraft;
    const title = content.split('\n')[0].slice(0, 48) || 'Prompt';
    setPromptDraft('');
    await run(() => adapter.addQueueItems(batch.id, [{ kind: 'prompt', title, content }]));
  }

  async function importFiles(files: FileList | null) {
    if (!batch || !files || files.length === 0) return;
    const items = await Promise.all(
      Array.from(files).map(async (file) => ({
        kind: 'file' as const,
        title: file.name,
        fileName: file.name,
        content: await file.text(),
      })),
    );
    await run(() => adapter.addQueueItems(batch.id, items));
  }

  function beginEdit(item: { id: string; title: string; content: string }) {
    setEditingId(item.id);
    setEditTitle(item.title);
    setEditContent(item.content);
  }

  async function saveEdit() {
    if (!batch || !editingId) return;
    await run(async () => {
      await adapter.updateQueueItem(batch.id, editingId, { title: editTitle, content: editContent });
      setEditingId(null);
    });
  }

  if (loading) return <LoadingState label="Carregando execução…" />;
  if (error) return <ErrorState message={error} />;

  if (!batch) {
    return (
      <div className="stack">
        <div className="view-header">
          <div><h1>Execução</h1><p>Espaço {workspaceId}</p></div>
        </div>
        <EmptyState title="Nenhum lote neste espaço" hint="Gere uma fila a partir do plano ou crie um lote manual." />
        <div className="row">
          <Button onClick={() => onNavigate('plan')}>Ir para o plano</Button>
          {!isDemo && (
            <Button
              variant="primary"
              disabled={disconnected || busy}
              onClick={() => void run(() => adapter.createBatch(workspaceId))}
            >
              <Plus size={14} aria-hidden="true" /> Novo lote manual
            </Button>
          )}
        </div>
      </div>
    );
  }

  const done = batch.items.filter((item) => item.status === 'done').length;
  const progress = batch.items.length === 0 ? 0 : Math.round((done / batch.items.length) * 100);
  const nextItem = batch.items[batch.cursor] ?? null;
  const failureMessage = currentAttempt?.status === 'failure'
    ? 'A terceira etapa e as seguintes permanecem pendentes até você retomar ou corrigir o fluxo.'
    : null;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Execução</h1>
          <p>{batch.name} · {shortId(batch.id)} · espaço {workspaceId}</p>
        </div>
        <div className="row">
          {batches.length > 1 && (
            <>
              <label className="sr-only" htmlFor="batch-select">Selecionar lote</label>
              <select
                id="batch-select"
                className="select"
                style={{ width: 'auto' }}
                value={batch.id}
                onChange={(event) => setSelectedBatchId(event.target.value)}
              >
                {batches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </>
          )}
          <StatusBadge status={batch.status} />
          {!isDemo && (
            <Button
              small
              disabled={disconnected || busy}
              onClick={() => void run(() => adapter.createBatch(workspaceId))}
            >
              <Plus size={14} aria-hidden="true" /> Novo lote
            </Button>
          )}
        </div>
      </div>

      {isDemo ? (
        <DemoNote>
          Execução simulada: nenhum comando é enviado ao PC. A pausa solicitada só é confirmada após a etapa atual.
        </DemoNote>
      ) : (
        <p className="panel-subtle">
          Fila persistida no backend. Prompts e ordem sobrevivem a reinícios; os controles de execução
          aguardam o motor real ({batch.sourceVersionId ? `origem: versão ${batch.sourceVersionId}` : 'lote manual'}).
        </p>
      )}

      {actionError && <ErrorState message={actionError} onRetry={() => setActionError(null)} />}
      {disconnected && (
        <ErrorState message="Último estado recebido preservado. Reconecte (modo Demo) ou verifique a API para habilitar ações." />
      )}

      <div className="view-grid">
        <div className="stack">
          <section className="panel">
            <div className="panel-header">
              <h2>Fila de execução</h2>
              <span className="panel-subtle">{batch.items.length} item(ns)</span>
            </div>
            <div className="panel-body stack">
              <div className="field">
                <label className="field-label" htmlFor="new-prompt">Colar prompt</label>
                <textarea
                  id="new-prompt"
                  className="textarea"
                  placeholder="Cole um prompt para adicionar à fila…"
                  value={promptDraft}
                  disabled={locked}
                  onChange={(event) => setPromptDraft(event.target.value)}
                />
              </div>
              <div className="row">
                <Button variant="primary" disabled={locked || !promptDraft.trim()} onClick={() => void addPrompt()}>
                  <CheckSquare size={14} aria-hidden="true" /> Adicionar prompt
                </Button>
                <div className="field">
                  <label className="field-label" htmlFor="queue-files">Importar arquivos .md/.txt</label>
                  <input
                    id="queue-files"
                    className="file-input"
                    type="file"
                    multiple
                    accept=".md,.txt,text/markdown,text/plain"
                    disabled={locked}
                    onChange={(event) => {
                      void importFiles(event.target.files);
                      event.target.value = '';
                    }}
                  />
                </div>
              </div>

              {batch.items.length === 0 ? (
                <EmptyState title="Fila vazia" hint="Adicione um prompt ou importe arquivos." />
              ) : (
                <div className="queue-list">
                  {batch.items.map((item, index) => {
                    const isCurrent = index === batch.cursor && (batch.status === 'running' || batch.status === 'pausing');
                    return (
                      <div key={item.id} className={`queue-item${isCurrent ? ' active' : ''}${item.status === 'failed' ? ' failed' : ''}`}>
                        <div className="queue-order" aria-hidden="true">{index + 1}</div>
                        <div style={{ minWidth: 0 }}>
                          <div className="queue-title">
                            {item.kind === 'file' && <FileText size={12} aria-hidden="true" />} {item.title}
                          </div>
                          <div className="queue-preview" title={item.content}>{item.content.replace(/\n/g, ' ')}</div>
                          <div className="row" style={{ marginTop: 4 }}>
                            <StatusBadge status={item.status} />
                            {item.fileName && <span className="panel-subtle">{item.fileName}</span>}
                          </div>
                          {editingId === item.id && (
                            <div className="edit-row">
                              <label className="sr-only" htmlFor={`edit-title-${item.id}`}>Título do item</label>
                              <input
                                id={`edit-title-${item.id}`}
                                className="input"
                                value={editTitle}
                                onChange={(event) => setEditTitle(event.target.value)}
                              />
                              <label className="sr-only" htmlFor={`edit-content-${item.id}`}>Conteúdo do item</label>
                              <textarea
                                id={`edit-content-${item.id}`}
                                className="textarea"
                                value={editContent}
                                onChange={(event) => setEditContent(event.target.value)}
                              />
                              <div className="row">
                                <Button small variant="primary" disabled={busy} onClick={() => void saveEdit()}>Salvar</Button>
                                <Button small onClick={() => setEditingId(null)}>Cancelar</Button>
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="queue-actions">
                          <IconButton label={`Editar ${item.title}`} disabled={locked} onClick={() => beginEdit(item)}>
                            <Pencil size={14} aria-hidden="true" />
                          </IconButton>
                          <IconButton label={`Mover ${item.title} para cima`} disabled={locked || index === 0} onClick={() => void run(() => adapter.moveQueueItem(batch.id, item.id, -1))}>
                            <ArrowUp size={14} aria-hidden="true" />
                          </IconButton>
                          <IconButton label={`Mover ${item.title} para baixo`} disabled={locked || index === batch.items.length - 1} onClick={() => void run(() => adapter.moveQueueItem(batch.id, item.id, 1))}>
                            <ArrowDown size={14} aria-hidden="true" />
                          </IconButton>
                          <IconButton label={`Remover ${item.title}`} disabled={locked} onClick={() => void run(() => adapter.removeQueueItem(batch.id, item.id))}>
                            <Trash2 size={14} aria-hidden="true" />
                          </IconButton>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Controles</h2>
              <Badge tone={engineUnavailable ? 'warning' : disconnected ? 'danger' : 'info'}>
                {engineUnavailable ? 'Motor pendente' : disconnected ? 'Desconectado' : 'Simulação'}
              </Badge>
            </div>
            <div className="panel-body">
              {engineUnavailable && (
                <p className="panel-subtle" style={{ marginBottom: 10 }}>
                  A execução real (OpenCode) ainda não está integrada. Os controles são habilitados apenas
                  no modo demonstração; a fila continua editável e persistida.
                </p>
              )}
              <div className="control-grid">
                <Button
                  variant="primary"
                  disabled={engineUnavailable || disconnected || busy || (batch.status !== 'idle' && batch.status !== 'completed')}
                  onClick={() => void run(() => adapter.startBatch(batch.id))}
                >
                  <Play size={14} aria-hidden="true" /> Iniciar
                </Button>
                <Button
                  disabled={engineUnavailable || disconnected || busy || batch.status !== 'running'}
                  onClick={() => void run(() => adapter.requestPause(batch.id))}
                >
                  <Pause size={14} aria-hidden="true" /> Pausar após etapa
                </Button>
                <Button
                  disabled={engineUnavailable || disconnected || busy || (batch.status !== 'paused' && batch.status !== 'failed')}
                  onClick={() => void run(() => adapter.resumeBatch(batch.id))}
                >
                  <RotateCcw size={14} aria-hidden="true" /> Retomar / corrigir
                </Button>
                <Button
                  variant="danger"
                  disabled={engineUnavailable || disconnected || busy || (batch.status !== 'running' && batch.status !== 'pausing')}
                  onClick={() => void run(() => adapter.cancelBatch(batch.id))}
                >
                  <Square size={14} aria-hidden="true" /> Cancelar
                </Button>
              </div>
              {batch.status === 'pausing' && (
                <p className="panel-subtle" style={{ marginTop: 10 }}>
                  <strong>Pausa solicitada</strong> — aguardando a etapa atual terminar. O estado confirmado aparecerá aqui.
                </p>
              )}
              {batch.status === 'paused' && (
                <p className="panel-subtle" style={{ marginTop: 10 }}>
                  <strong>Pausa confirmada</strong> — nenhuma etapa está em execução. Use "Retomar / corrigir".
                </p>
              )}
              {failureMessage && <p className="panel-subtle" style={{ marginTop: 10 }}>{failureMessage}</p>}
            </div>
          </section>
        </div>

        <div className="stack">
          <section className="panel">
            <div className="panel-header"><h2>Progresso</h2><StatusBadge status={batch.status} /></div>
            <div className="panel-body stack">
              <div className="progress-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso do lote">
                <div className={`progress-fill${batch.status === 'failed' ? ' failed' : ''}`} style={{ width: `${progress}%` }} />
              </div>
              <div className="spread">
                <span className="panel-subtle">{done} de {batch.items.length} etapa(s)</span>
                <strong>{progress}%</strong>
              </div>
              <div className="pr-card">
                <div className="spread">
                  <strong style={{ fontSize: '0.8rem' }}>{nextItem ? `Próxima: ${nextItem.title}` : 'Fila esgotada'}</strong>
                  {nextItem && <StatusBadge status={nextItem.status} />}
                </div>
                <p className="panel-subtle" style={{ marginTop: 6 }}>
                  Tentativa atual: {currentAttempt ? shortId(currentAttempt.id) : 'nenhuma'}
                  {currentAttempt && ` · ${formatTime(currentAttempt.startedAt)}`}
                </p>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>Saída e resultado</h2>
              {currentAttempt && <StatusBadge status={currentAttempt.status} />}
            </div>
            <div className="panel-body stack">
              {!currentAttempt ? (
                <EmptyState title="Sem saída" hint="Inicie o lote para ver a execução." />
              ) : (
                <>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Prompt executado</span>
                    <pre className="console">{currentAttempt.prompt}</pre>
                  </div>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Saída</span>
                    <ConsoleOutput text={currentAttempt.output} />
                  </div>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Resultado</span>
                    <p className="objective">{currentAttempt.result || 'Em execução…'}</p>
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h2>Resultados por etapa</h2></div>
            <div className="panel-body tight">
              {batchAttempts.length === 0 ? (
                <p className="panel-subtle">Nenhuma tentativa neste lote.</p>
              ) : (
                <div className="history-list">
                  {batchAttempts.map((attempt) => (
                    <div key={attempt.id} className="history-item">
                      <div className="spread">
                        <strong>Etapa {attempt.stepIndex + 1} · {attempt.itemTitle}</strong>
                        <StatusBadge status={attempt.status} />
                      </div>
                      <small>{shortId(attempt.id)} · {formatTime(attempt.startedAt)}</small>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function ConsoleOutput({ text }: { text: string }) {
  const lines = text.split('\n');
  return (
    <pre className="console">
      {lines.map((line, index) => {
        const tone = /^\[erro\]|^\[aviso\]/.test(line) ? 'err' : /^\[ok\]/.test(line) ? 'ok' : undefined;
        return (
          <span key={index} className={tone}>
            {line}{index < lines.length - 1 ? '\n' : ''}
          </span>
        );
      })}
    </pre>
  );
}
