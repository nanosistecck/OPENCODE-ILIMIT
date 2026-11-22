import { GitBranch, Link2 } from 'lucide-react';
import { useState } from 'react';
import {
  Badge, DemoNote, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { useMode, useSnapshot } from '../state/AppContext';
import { useWorkspaceResource } from '../state/useWorkspaceResource';
import { shortId, formatDateTime } from '../utils/format';

export function HistoryView() {
  const snapshot = useSnapshot();
  const { mode } = useMode();
  const { loading, error } = useWorkspaceResource();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const workspaceId = snapshot.activeWorkspaceId;
  const batches = snapshot.batchesByWorkspace[workspaceId] ?? [];
  const attempts = snapshot.attemptsByWorkspace[workspaceId] ?? [];
  const workspace = snapshot.workspaces.find((item) => item.id === workspaceId);
  const selected = attempts.find((attempt) => attempt.id === selectedId) ?? attempts[0] ?? null;

  if (loading) return <LoadingState label="Carregando histórico…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Histórico</h1>
          <p>Lotes e tentativas do espaço {workspaceId}.</p>
        </div>
        <Badge tone="info">Vínculo por ID</Badge>
      </div>

      {mode === 'demo' ? (
        <DemoNote>
          Tentativas simuladas. Cada tentativa registra o prompt executado, a saída, o resultado e a branch exibida —
          o vínculo real é o ID do espaço.
        </DemoNote>
      ) : (
        <p className="panel-subtle">
          Lotes vêm do banco local. Tentativas aparecerão quando o motor de fila for integrado.
        </p>
      )}

      {attempts.length === 0 && batches.length === 0 ? (
        <EmptyState title="Nenhum lote ou tentativa neste espaço" hint="Execute um lote na aba Execução para gerar histórico." />
      ) : (
        <div className="history-layout">
          <div className="stack">
            <section className="panel">
              <div className="panel-header"><h2>Lotes</h2><span className="panel-subtle">{batches.length}</span></div>
              <div className="panel-body tight">
                <div className="history-list">
                  {batches.map((batch) => (
                    <div key={batch.id} className="history-item">
                      <div className="spread">
                        <strong>{batch.name}</strong>
                        <StatusBadge status={batch.status} />
                      </div>
                      <small>{shortId(batch.id)} · {batch.items.length} item(ns)</small>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header"><h2>Tentativas</h2><span className="panel-subtle">{attempts.length}</span></div>
              <div className="panel-body tight">
                {attempts.length === 0 ? (
                  <EmptyState title="Sem tentativas" hint="O lote ainda não foi executado." />
                ) : (
                  <div className="history-list">
                    {attempts.map((attempt) => (
                      <button
                        key={attempt.id}
                        type="button"
                        className={`history-item${selected?.id === attempt.id ? ' active' : ''}`}
                        aria-pressed={selected?.id === attempt.id}
                        onClick={() => setSelectedId(attempt.id)}
                      >
                        <div className="spread">
                          <strong>{attempt.itemTitle}</strong>
                          <StatusBadge status={attempt.status} />
                        </div>
                        <small>Etapa {attempt.stepIndex + 1} · {formatDateTime(attempt.startedAt)}</small>
                        <small>{shortId(attempt.id)}</small>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>

          <section className="panel" aria-label="Detalhe da tentativa">
            <div className="panel-header">
              <h2>Detalhe da tentativa</h2>
              {selected && <StatusBadge status={selected.status} />}
            </div>
            <div className="panel-body">
              {!selected ? (
                <EmptyState title="Selecione uma tentativa" />
              ) : (
                <div className="attempt-detail">
                  <KeyValue label="Item">{selected.itemTitle}</KeyValue>
                  <KeyValue label="Etapa">{selected.stepIndex + 1}</KeyValue>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Prompt executado</span>
                    <pre className="console">{selected.prompt}</pre>
                  </div>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Saída</span>
                    <pre className="console">{selected.output || 'Sem saída registrada.'}</pre>
                  </div>
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="kv-label">Resultado</span>
                    <p className="objective">{selected.result || 'Sem resultado registrado.'}</p>
                  </div>
                  <div className="pr-card">
                    <div className="spread">
                      <strong className="row"><Link2 size={14} aria-hidden="true" /> Vínculo com a branch</strong>
                      <GitBranch size={14} aria-hidden="true" />
                    </div>
                    <div className="stack" style={{ marginTop: 8, gap: 4 }}>
                      <KeyValue label="Branch (exibição)"><span className="mono">{selected.branch}</span></KeyValue>
                      <KeyValue label="ID do espaço (vínculo)"><span className="mono">{selected.workspaceRef}</span></KeyValue>
                      <KeyValue label="ID do lote"><span className="mono">{shortId(selected.batchId)}</span></KeyValue>
                    </div>
                  </div>
                  {workspace && (
                    <p className="panel-subtle">
                      A branch exibida é {workspace.branch}; a consulta ao histórico usa {workspace.id}.
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
