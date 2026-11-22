import { ArrowRight, ClipboardCheck, FileStack, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import {
  Badge, Button, Collapsible, DemoNote, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { useAdapter, useMode, useSnapshot } from '../state/AppContext';
import { useWorkspaceResource } from '../state/useWorkspaceResource';
import type { ViewId } from '../domain/navigation';
import type { ID, PlanInput, PlanStepInput } from '../domain/types';
import { formatDateTime } from '../utils/format';

export function PlanView({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const { mode } = useMode();
  const { loading, error } = useWorkspaceResource();
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);

  const plan = snapshot.plansByWorkspace[snapshot.activeWorkspaceId];
  const disconnected = mode === 'demo'
    ? snapshot.connection !== 'connected'
    : snapshot.apiStatus !== 'ok' || snapshot.connection === 'error';

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

  if (loading) return <LoadingState label="Carregando plano…" />;
  if (error) return <ErrorState message={error} />;
  if (!plan) return <EmptyState title="Sem plano neste espaço" hint="Cadastre um plano na área de configurações." />;

  const dependencyTitle = (id: string) => plan.steps.find((step) => step.id === id)?.title ?? id;
  const hasVersions = plan.versions.length > 0;

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Plano</h1>
          <p>Espaço {snapshot.activeWorkspaceId} · revise e transforme as etapas em fila.</p>
        </div>
        <Badge tone="info">Versão {plan.version}</Badge>
      </div>

      {mode === 'demo' ? (
        <DemoNote>
          Plano de exemplo. A revisão e a geração de fila são simulações locais; o backend confirmará essas ações depois.
        </DemoNote>
      ) : (
        <p className="panel-subtle">
          Plano persistido no backend. Cada salvamento cria uma nova versão imutável; lotes antigos mantêm sua origem.
        </p>
      )}

      {actionError && <ErrorState message={actionError} onRetry={() => setActionError(null)} />}

      <section className="panel">
        <div className="panel-header">
          <h2>Objetivo</h2>
          <StatusBadge status={plan.status} />
        </div>
        <div className="panel-body stack">
          <p className="objective">{plan.objective || 'Plano sem objetivo cadastrado.'}</p>
          <div className="row">
            {mode === 'connected' && (
              <Button
                disabled={disconnected || busy}
                onClick={() => setEditing((value) => !value)}
              >
                <Plus size={14} aria-hidden="true" />
                {editing ? 'Fechar editor' : 'Editar / nova versão'}
              </Button>
            )}
            <Button
              variant="primary"
              disabled={disconnected || busy || plan.status === 'in_review' || plan.steps.length === 0}
              onClick={() => void run(() => adapter.reviewPlan(snapshot.activeWorkspaceId))}
            >
              <ClipboardCheck size={14} aria-hidden="true" />
              {plan.status === 'in_review' ? 'Em revisão' : 'Revisar plano'}
            </Button>
            <Button
              disabled={disconnected || busy || plan.steps.length === 0}
              onClick={() => void run(async () => {
                if (mode === 'connected') {
                  const current = plan.versions.find((version) => version.version === plan.version);
                  await adapter.generateQueueFromVersion(
                    snapshot.activeWorkspaceId,
                    current?.id ?? String(plan.version),
                  );
                } else {
                  await adapter.generateQueue(snapshot.activeWorkspaceId);
                }
                onNavigate('execution');
              })}
            >
              <FileStack size={14} aria-hidden="true" />
              Gerar fila {hasVersions ? `da v${plan.version}` : 'simulada'}
            </Button>
            {disconnected && <span className="panel-subtle">Ações desabilitadas: API/PC indisponível.</span>}
          </div>
        </div>
      </section>

      {mode === 'connected' && editing && (
        <PlanEditor
          key={plan.version}
          objective={plan.objective}
          steps={plan.steps.map((step) => ({
            id: step.id,
            order: step.order,
            title: step.title,
            description: step.description,
            dependencies: step.dependencies,
            acceptanceCriteria: step.acceptanceCriteria,
            prompt: step.prompt ?? step.description,
            status: step.status,
          }))}
          busy={busy}
          onSave={(value) => void run(async () => {
            await adapter.savePlan(snapshot.activeWorkspaceId, value);
            setEditing(false);
          })}
        />
      )}

      <Collapsible title={`Versões do plano (${plan.versions.length})`}>
        {plan.versions.length === 0 ? (
          <p className="panel-subtle">Nenhuma versão anterior registrada.</p>
        ) : (
          <div className="stack">
            {plan.versions.map((version) => (
              <div key={version.id ?? version.version} className="queue-item">
                <div className="queue-order">v{version.version}</div>
                <div style={{ minWidth: 0 }}>
                  <div className="queue-title">{version.objective || 'Sem objetivo'}</div>
                  <div className="queue-preview">
                    {formatDateTime(version.createdAt)} · {version.steps.length} etapa(s)
                  </div>
                </div>
                <div className="queue-actions">
                  <Button
                    small
                    disabled={disconnected || busy}
                    onClick={() => void run(async () => {
                      await adapter.generateQueueFromVersion(
                        snapshot.activeWorkspaceId,
                        version.id ?? String(version.version),
                      );
                      onNavigate('execution');
                    })}
                  >
                    Gerar fila
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Collapsible>

      <section className="panel">
        <div className="panel-header">
          <h2>Etapas em ordem</h2>
          <span className="panel-subtle">{plan.steps.length} etapa(s)</span>
        </div>
        <div className="panel-body">
          <div className="steps">
            {plan.steps.map((step) => (
              <article key={step.id} className="step">
                <div className="step-head">
                  <span className="step-index" aria-hidden="true">{step.order}</span>
                  <span className="step-title">{step.title}</span>
                  <StatusBadge status={step.status} />
                </div>
                <div className="step-body">
                  <KeyValue label="Descrição">{step.description}</KeyValue>
                  <KeyValue label="Dependências">
                    {step.dependencies.length === 0 ? 'Nenhuma' : step.dependencies.map(dependencyTitle).join(', ')}
                  </KeyValue>
                  <KeyValue label="Critério de aceite">{step.acceptanceCriteria}</KeyValue>
                  {step.prompt && <KeyValue label="Prompt da fila">{step.prompt}</KeyValue>}
                </div>
              </article>
            ))}
          </div>
          <p className="panel-subtle" style={{ marginTop: 12 }}>
            <ArrowRight size={12} aria-hidden="true" /> "Gerar fila" cria um lote com base na versão escolhida.
          </p>
        </div>
      </section>
    </div>
  );
}

function PlanEditor({
  objective,
  steps,
  busy,
  onSave,
}: {
  objective: string;
  steps: PlanStepInput[];
  busy: boolean;
  onSave: (plan: PlanInput) => void;
}) {
  const [draftObjective, setDraftObjective] = useState(objective);
  const [draftSteps, setDraftSteps] = useState<PlanStepInput[]>(steps);

  function updateStep(index: number, patch: Partial<PlanStepInput>) {
    setDraftSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  function addStep() {
    const order = draftSteps.length + 1;
    setDraftSteps((current) => [
      ...current,
      {
        id: `step-${Date.now()}-${order}` as ID,
        order,
        title: `Etapa ${order}`,
        description: '',
        dependencies: [],
        acceptanceCriteria: '',
        prompt: '',
        status: 'pending',
      },
    ]);
  }

  return (
    <section className="panel">
      <div className="panel-header"><h2>Editor de plano (nova versão)</h2></div>
      <div className="panel-body stack">
        <div className="field">
          <label className="field-label" htmlFor="plan-objective">Objetivo</label>
          <input
            id="plan-objective"
            className="input"
            value={draftObjective}
            onChange={(event) => setDraftObjective(event.target.value)}
          />
        </div>

        {draftSteps.map((step, index) => (
          <div key={step.id} className="step plan-editor-step">
            <div className="spread">
              <strong style={{ fontSize: '0.82rem' }}>Etapa {index + 1}</strong>
              <Button
                small
                variant="danger"
                disabled={busy || draftSteps.length <= 1}
                onClick={() => setDraftSteps((current) =>
                  current.filter((_, i) => i !== index).map((item, i) => ({ ...item, order: i + 1 })),
                )}
                aria-label={`Remover etapa ${index + 1}`}
              >
                <Trash2 size={13} aria-hidden="true" /> Remover
              </Button>
            </div>
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
              <label className="field-label" htmlFor={`step-desc-${index}`}>Descrição</label>
              <input
                id={`step-desc-${index}`}
                className="input"
                value={step.description}
                onChange={(event) => updateStep(index, { description: event.target.value })}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor={`step-deps-${index}`}>Dependências (IDs separados por vírgula)</label>
              <input
                id={`step-deps-${index}`}
                className="input"
                value={step.dependencies.join(', ')}
                onChange={(event) => updateStep(index, {
                  dependencies: event.target.value.split(',').map((value) => value.trim()).filter(Boolean),
                })}
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
              <label className="field-label" htmlFor={`step-prompt-${index}`}>Prompt copiado para a fila</label>
              <textarea
                id={`step-prompt-${index}`}
                className="textarea"
                value={step.prompt}
                onChange={(event) => updateStep(index, { prompt: event.target.value })}
              />
            </div>
          </div>
        ))}

        <div className="row">
          <Button disabled={busy} onClick={addStep}><Plus size={14} aria-hidden="true" /> Adicionar etapa</Button>
          <Button
            variant="primary"
            disabled={busy || !draftObjective.trim() || draftSteps.length === 0}
            onClick={() => onSave({ objective: draftObjective.trim(), steps: draftSteps })}
          >
            Salvar nova versão
          </Button>
        </div>
        <p className="panel-subtle">
          Dependências devem apontar para etapas desta versão, vir antes na ordem e não formar ciclos.
        </p>
      </div>
    </section>
  );
}
