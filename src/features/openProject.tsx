import { ArrowRight, Check, FolderSearch, RefreshCw, ShieldAlert, X } from 'lucide-react';
import { useState } from 'react';
import {
  Badge, Button, Collapsible, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { useAdapter, useMode } from '../state/AppContext';
import type { DiscoveryPreview } from '../domain/types';
import type { ViewId } from '../domain/navigation';

const SOURCE_LABEL: Record<string, string> = {
  salvo: 'Preferência salva', git: 'Git local', github: 'GitHub', local: 'Ferramenta local',
  padrao: 'Valor padrão',
};

export function OpenProjectDialog({
  onClose,
  onNavigate,
}: {
  onClose: () => void;
  onNavigate: (view: ViewId) => void;
}) {
  const adapter = useAdapter();
  const { mode } = useMode();
  const [path, setPath] = useState('');
  const [data, setData] = useState<DiscoveryPreview | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na descoberta.');
    } finally {
      setBusy(false);
    }
  }

  function applyChoice(key: string, value: string) {
    setChoices((current) => ({ ...current, [key]: value }));
    setData((current) => current ? { ...current, [key]: value } : current);
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="panel modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="open-project-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel-header">
          <h2 id="open-project-title">Abrir projeto</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fechar">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
        <div className="panel-body stack">
          <p className="panel-subtle">
            <FolderSearch size={13} aria-hidden="true" /> Informe a pasta no computador que executa o backend.
            Uma subpasta é resolvida para a raiz da worktree.
          </p>
          {mode === 'connected' && (
            <p className="panel-subtle">
              <ShieldAlert size={13} aria-hidden="true" /> Este fluxo é local; com acesso remoto ativo o backend bloqueia o cadastro de caminhos.
            </p>
          )}
          <div className="composer">
            <label className="sr-only" htmlFor="project-path">Pasta do projeto</label>
            <input
              id="project-path"
              className="input"
              value={path}
              placeholder="C:\repos\meu-projeto"
              onChange={(event) => setPath(event.target.value)}
            />
            <Button
              variant="primary"
              disabled={busy || !path.trim()}
              onClick={() => void run(async () => {
                setData(await adapter.discoveryPreview(path.trim()));
                setChoices({});
              })}
            >
              Detectar
            </Button>
          </div>

          {error && <ErrorState message={error} onRetry={() => setError('')} />}
          {busy && <LoadingState label="Detectando configuração…" />}

          {data && !busy && (
            <>
              <div className="discovery-grid">
                <div>
                  <span className="field-label">Projeto</span>
                  <strong>{data.projectName}</strong>
                  <Badge tone="info">{SOURCE_LABEL[data.sources.project ?? 'git'] ?? 'Detectado'}</Badge>
                </div>
                <div>
                  <span className="field-label">Branch de trabalho</span>
                  <strong className="mono">{data.branch || '—'}</strong>
                  <Badge tone={data.ready ? 'success' : 'warning'}>
                    {data.ready ? 'Worktree apta' : 'Requer decisão'}
                  </Badge>
                </div>
                <div>
                  <span className="field-label">Pasta</span>
                  <strong className="mono" style={{ overflowWrap: 'anywhere' }}>{data.path}</strong>
                </div>
                <div>
                  <span className="field-label">Destino do PR</span>
                  <strong className="mono">{data.prRepository || '—'}</strong>
                  <span className="panel-subtle">base {data.prBase || '—'}</span>
                </div>
                <div>
                  <span className="field-label">OpenCode</span>
                  <StatusBadge status={data.tools.openCode.found ? 'success' : 'warning'} />
                  <span className="panel-subtle">{data.tools.openCode.version || 'não detectado'}</span>
                </div>
              </div>

              {data.existingPr && (
                <div className="pr-card">
                  <div className="spread">
                    <strong>PR ativo confirmado #{data.existingPr.number}</strong>
                    <Badge tone="success">GitHub</Badge>
                  </div>
                  <p className="panel-subtle">{data.existingPr.title} · base {data.existingPr.base}</p>
                  <a className="btn" href={data.existingPr.url} target="_blank" rel="noopener noreferrer">Abrir no GitHub</a>
                </div>
              )}

              {data.ambiguities.length > 0 && (
                <div className="stack" style={{ gap: 6 }}>
                  <span className="field-label">Escolhas necessárias</span>
                  {data.ambiguities.map((ambiguity) => (
                    <div key={ambiguity.key} className="field">
                      <label className="field-label" htmlFor={`choice-${ambiguity.key}`}>{ambiguity.reason}</label>
                      <select
                        id={`choice-${ambiguity.key}`}
                        className="select"
                        value={choices[ambiguity.key] ?? ambiguity.options[0] ?? ''}
                        onChange={(event) => applyChoice(ambiguity.key, event.target.value)}
                      >
                        {ambiguity.options.map((option, index) => (
                          <option key={`${ambiguity.key}-${index}`} value={option}>{option}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              )}

              <Collapsible title="Informações adicionais">
                <KeyValue label="Upstream"><span className="mono">{data.upstream || 'não configurado'}</span></KeyValue>
                <KeyValue label="Remoto de publicação"><span className="mono">{data.publishRemote || '—'}</span></KeyValue>
                <KeyValue label="Base do plano"><span className="mono">{data.baseBranch || '—'}</span></KeyValue>
                <KeyValue label="HEAD"><span className="mono">{data.head.slice(0, 12) || '—'}</span></KeyValue>
                <p className="panel-subtle">
                  Origem dos dados: {Object.entries(data.sources).map(([key, value]) =>
                    `${key}=${SOURCE_LABEL[value] ?? value}`).join(' · ')}
                </p>
                {data.notes.map((note) => <p key={note} className="panel-subtle">· {note}</p>)}
                {data.worktrees.length > 0 && (
                  <div className="stack" style={{ gap: 4 }}>
                    <span className="field-label">Worktrees do repositório</span>
                    {data.worktrees.map((item) => (
                      <div key={item.path} className="history-item">
                        <strong className="mono">{item.branch || 'HEAD destacado'}</strong>
                        <small style={{ overflowWrap: 'anywhere' }}>{item.path}</small>
                      </div>
                    ))}
                  </div>
                )}
              </Collapsible>

              <div className="row">
                <Button
                  variant="primary"
                  disabled={busy || !data.branch}
                  onClick={() => void run(async () => {
                    const result = await adapter.discoveryOpen(path.trim(), choices);
                    await adapter.setActiveWorkspace(result.workspaceId);
                    await adapter.refresh();
                    onNavigate('execution');
                    onClose();
                  })}
                >
                  <Check size={14} aria-hidden="true" /> Ir para a fila
                </Button>
                <Button disabled={busy} onClick={() => void run(async () => {
                  setData(await adapter.discoveryPreview(path.trim(), true));
                })}>
                  <RefreshCw size={13} aria-hidden="true" /> Atualizar descoberta
                </Button>
              </div>
              {!data.branch && (
                <EmptyState
                  title="Branch de trabalho não detectada"
                  hint="Abra uma worktree em uma branch de trabalho ou escolha uma existente na seção de detalhes."
                />
              )}
            </>
          )}

          <p className="panel-subtle">
            <ArrowRight size={12} aria-hidden="true" /> Nenhuma alteração é feita no Git até você usar os fluxos explícitos de worktree, commit ou PR.
          </p>
        </div>
      </section>
    </div>
  );
}
