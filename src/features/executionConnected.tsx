import {
  CirclePlay, RefreshCw, Square, Terminal, TestTube2, XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import {
  Badge, Button, Collapsible, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { useAdapter, useSnapshot } from '../state/AppContext';
import type { LogChunk, OpenCodeStatus, QueueBatch, QueueState } from '../domain/types';
import { formatDateTime, shortId } from '../utils/format';

export function ConnectedExecutionView() {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const workspaceId = snapshot.activeWorkspaceId;

  const [state, setState] = useState<QueueState | null>(null);
  const [opencode, setOpencode] = useState<OpenCodeStatus | null>(null);
  const [executable, setExecutable] = useState('');
  const [model, setModel] = useState('');
  const [agent, setAgent] = useState('');
  const [timeoutValue, setTimeoutValue] = useState('600');
  const [diagnostic, setDiagnostic] = useState('');
  const [selectedAttempt, setSelectedAttempt] = useState<string | null>(null);
  const [log, setLog] = useState<LogChunk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const next = await adapter.getQueueState(workspaceId);
      setState(next);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao consultar a fila.');
    }
  }, [adapter, workspaceId]);

  const loadOpencode = useCallback(async () => {
    try {
      const status = await adapter.getOpenCodeStatus();
      setOpencode(status);
      setExecutable(status.configured.executable);
      setModel(status.configured.model);
      setAgent(status.configured.agent);
      setTimeoutValue(status.configured.timeout || '600');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao consultar o OpenCode.');
    }
  }, [adapter]);

  useEffect(() => {
    setLoaded(false);
    void load();
    void loadOpencode();
    const timer = window.setInterval(() => { void load(); }, 1000);
    const slowTimer = window.setInterval(() => { void loadOpencode(); }, 10000);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(slowTimer);
    };
  }, [load, loadOpencode]);

  const batch: QueueBatch | undefined = state?.batches?.[0];
  const attempts = batch?.attempts ?? state?.attempts ?? [];
  const current = attempts.find((attempt) => attempt.status === 'running')
    ?? (selectedAttempt ? attempts.find((attempt) => attempt.id === selectedAttempt) : undefined);

  useEffect(() => {
    if (!current || current.status !== 'running') return;
    let active = true;
    const read = async (offset: number) => {
      try {
        const chunk = await adapter.getAttemptLog(current.id, offset);
        if (!active) return;
        setLog((previous) => ({
          text: (offset === 0 ? '' : previous?.text ?? '') + chunk.text,
          nextOffset: chunk.nextOffset,
          done: chunk.done,
        }));
      } catch {
        // O log pode não existir ainda; a próxima consulta tenta de novo.
      }
    };
    void read(log?.nextOffset ?? 0);
    const timer = window.setInterval(() => { void read(log?.nextOffset ?? 0); }, 700);
    return () => { active = false; window.clearInterval(timer); };
  }, [adapter, current?.id, current?.status, log?.nextOffset]);

  async function run(action: () => Promise<unknown>, message?: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (message) setDiagnostic(message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na ação.');
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <LoadingState label="Carregando estado do motor…" />;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Execução</h1>
          <p>Espaço {workspaceId} · fila e tentativas confirmadas pelo backend.</p>
        </div>
        <div className="row">
          <Badge tone={opencode?.found ? 'success' : 'danger'}>
            {opencode?.found ? `OpenCode ${shortId(opencode.version)}` : 'OpenCode ausente'}
          </Badge>
          <Button small disabled={busy} onClick={() => void run(() => loadOpencode())}>
            <RefreshCw size={13} aria-hidden="true" /> Atualizar
          </Button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />}

      <Collapsible title="Configuração do OpenCode" badge={<span className="panel-subtle">executável local</span>}>
        <div className="setup-grid">
          <div className="field">
            <label className="field-label" htmlFor="oc-executable">Caminho do executável (neste computador)</label>
            <input
              id="oc-executable"
              className="input"
              value={executable}
              onChange={(event) => setExecutable(event.target.value)}
              placeholder={opencode?.path || 'opencode'}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="oc-model">Modelo (opcional)</label>
            <input
              id="oc-model"
              className="input"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="provider/model"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="oc-agent">Agente (opcional)</label>
            <input
              id="oc-agent"
              className="input"
              value={agent}
              onChange={(event) => setAgent(event.target.value)}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="oc-timeout">Timeout (segundos)</label>
            <input
              id="oc-timeout"
              className="input"
              value={timeoutValue}
              onChange={(event) => setTimeoutValue(event.target.value)}
            />
          </div>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => void run(
              () => adapter.putOpenCodeConfig({ executable, model, agent, timeout: timeoutValue }),
              'Configuração salva.',
            )}
          >
            Salvar configuração
          </Button>
          <Button disabled={busy} onClick={() => void run(() => adapter.getOpenCodeStatus())}>
            <TestTube2 size={14} aria-hidden="true" /> Testar conexão
          </Button>
          <Button disabled={busy} onClick={() => void run(async () => {
            const result = await adapter.testOpenCode();
            setDiagnostic(`exit=${result.exitCode}\n${result.stdout}${result.stderr}`);
          })}>
            Enviar diagnóstico
          </Button>
        </div>
        {opencode && (
          <p className="panel-subtle">
            JSON: {opencode.capabilities.jsonFormat ? 'sim' : 'não'} · sessão:{' '}
            {opencode.capabilities.session ? 'sim' : 'não'} · modelo:{' '}
            {opencode.capabilities.model ? 'sim' : 'não'}
          </p>
        )}
        {diagnostic && <pre className="console" tabIndex={0}>{diagnostic}</pre>}
      </Collapsible>

      {!batch ? (
        <EmptyState title="Nenhum lote neste espaço" hint="Gere uma fila a partir do plano ou crie um lote manual." />
      ) : (
        <>
          <section className="panel">
            <div className="panel-header">
              <h2>{batch.name}</h2>
              <div className="row">
                <StatusBadge status={batch.status} />
                {batch.pauseRequested && <Badge tone="warning">Pausa solicitada</Badge>}
              </div>
            </div>
            <div className="panel-body stack">
              <div className="control-grid">
                <Button
                  variant="primary"
                  disabled={busy || !['idle', 'completed'].includes(batch.status)}
                  onClick={() => void run(() => adapter.startBatch(batch.id))}
                >
                  <CirclePlay size={14} aria-hidden="true" /> Executar lote
                </Button>
                <Button
                  disabled={busy || batch.status !== 'running'}
                  onClick={() => void run(() => adapter.requestPause(batch.id))}
                >
                  Pausar após esta etapa
                </Button>
                <Button
                  disabled={busy || !['paused', 'interrupted', 'failed'].includes(batch.status)}
                  onClick={() => void run(() => adapter.resumeBatch(batch.id))}
                >
                  Retomar
                </Button>
                <Button
                  variant="danger"
                  disabled={busy || !['running', 'pausing'].includes(batch.status)}
                  onClick={() => void run(() => adapter.cancelBatch(batch.id))}
                >
                  <Square size={14} aria-hidden="true" /> Cancelar
                </Button>
              </div>
              {batch.status === 'pausing' && (
                <p className="panel-subtle">
                  Pausa solicitada — a etapa atual ainda está terminando. A confirmação aparecerá quando o backend responder.
                </p>
              )}
              {batch.status === 'paused' && (
                <p className="panel-subtle">Pausa confirmada — nenhuma etapa está em execução.</p>
              )}
              {batch.blockReason && (
                <div className="demo-banner" role="status">
                  <XCircle size={16} aria-hidden="true" />
                  <span>Execução bloqueada: {batch.blockReason}</span>
                </div>
              )}
              {batch.lastError && <p className="panel-subtle">Último erro: {batch.lastError}</p>}
              <div className="row">
                <Badge tone="info">Etapa {Math.min(batch.cursor + 1, batch.items.length)} de {batch.items.length}</Badge>
                <Badge tone="neutral">{batch.items.filter((item) => item.status === 'done').length} concluída(s)</Badge>
              </div>
            </div>
          </section>

          <div className="view-grid">
            <div className="stack">
              <section className="panel">
                <div className="panel-header"><h2>Fila</h2><span className="panel-subtle">{batch.items.length} item(ns)</span></div>
                <div className="panel-body tight">
                  {batch.items.map((item) => (
                    <div key={item.id} className="history-item">
                      <div className="spread">
                        <strong>{item.order + 1}. {item.title}</strong>
                        <StatusBadge status={item.status} />
                      </div>
                      <small>{item.content.slice(0, 120).replace(/\n/g, ' ')}</small>
                      {item.acceptanceCriteria && <small>Aceite: {item.acceptanceCriteria}</small>}
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header"><h2>Tentativas</h2><span className="panel-subtle">{attempts.length}</span></div>
                <div className="panel-body tight">
                  {attempts.length === 0 ? (
                    <EmptyState title="Sem tentativas" hint="Execute o lote para registrar tentativas." />
                  ) : (
                    <div className="history-list">
                      {attempts.map((attempt) => (
                        <button
                          key={attempt.id}
                          type="button"
                          className={`history-item${current?.id === attempt.id ? ' active' : ''}`}
                          onClick={() => {
                            setSelectedAttempt(attempt.id);
                            setLog(null);
                          }}
                        >
                          <div className="spread">
                            <strong>{attempt.itemId.slice(-8)} · {attempt.status}</strong>
                            <StatusBadge status={attempt.status} />
                          </div>
                          <small>{formatDateTime(attempt.createdAt)} · {shortId(attempt.id)}</small>
                          {attempt.error && <small>{attempt.error.slice(0, 140)}</small>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>

            <div className="stack">
              {current ? (
                <section className="panel">
                  <div className="panel-header">
                    <h2>Tentativa atual</h2>
                    <StatusBadge status={current.status} />
                  </div>
                  <div className="panel-body stack">
                    <KeyValue label="Prompt enviado"><span className="mono">{current.promptSnapshot.slice(0, 180)}</span></KeyValue>
                    <KeyValue label="Sessão"><span className="mono">{current.sessionId || '—'}</span></KeyValue>
                    <KeyValue label="Modelo"><span className="mono">{current.observedModel || current.requestedModel || 'padrão'}</span></KeyValue>
                    <KeyValue label="HEAD inicial"><span className="mono">{shortId(current.headBefore || '')}</span></KeyValue>
                    <KeyValue label="HEAD final"><span className="mono">{shortId(current.headAfter || '')}</span></KeyValue>
                    {current.statusBefore && (
                      <p className="panel-subtle">
                        Alterações já presentes: {current.statusBefore.total} arquivo(s)
                      </p>
                    )}
                    {current.error && <p className="panel-subtle">{current.error}</p>}
                    <div className="stack" style={{ gap: 4 }}>
                      <span className="field-label"><Terminal size={12} aria-hidden="true" /> Saída incremental</span>
                      <pre className="console diff-view" tabIndex={0}>{log?.text || 'Aguardando saída…'}</pre>
                      {log && !log.done && <p className="panel-subtle">Carregando trechos…</p>}
                    </div>
                    {['failure', 'inconclusive', 'interrupted', 'cancelled'].includes(current.status) && (
                      <div className="row">
                        <Button
                          variant="primary"
                          disabled={busy}
                          onClick={() => void run(() => adapter.retryAttempt(current.id, false))}
                        >
                          Tentar novamente
                        </Button>
                        {current.sessionId && (
                          <Button
                            disabled={busy}
                            onClick={() => void run(() => adapter.retryAttempt(current.id, true))}
                          >
                            Continuar sessão
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                </section>
              ) : (
                <EmptyState title="Nenhuma tentativa selecionada" />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
