import { Check, ExternalLink, GitCommitHorizontal, Rocket, Send, ShieldAlert } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import {
  Badge, Button, Collapsible, EmptyState, ErrorState, KeyValue, StatusBadge,
} from '../components/common';
import { useAdapter, useSnapshot } from '../state/AppContext';
import type { DeliveryPreview, DeliveryPrPreview, DeliveryState, GitStatus } from '../domain/types';
import { formatDateTime, shortId } from '../utils/format';

export function DeliveryPanel() {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const workspaceId = snapshot.activeWorkspaceId;
  const git = snapshot.gitByWorkspace[workspaceId];

  const [state, setState] = useState<DeliveryState | null>(null);
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [preview, setPreview] = useState<DeliveryPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [remote, setRemote] = useState('');
  const [prPreview, setPrPreview] = useState<DeliveryPrPreview | null>(null);
  const [base, setBase] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [diffText, setDiffText] = useState<{ file: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!workspaceId || !git?.linked) return;
    try {
      const [nextState, nextStatus] = await Promise.all([
        adapter.getDeliveryState(workspaceId),
        adapter.getGitStatus(workspaceId),
      ]);
      setState(nextState);
      setStatus(nextStatus);
      setRemote((current) => current || nextState.remotes[0]?.name || '');
      setBase((current) => current || nextState.pullRequests[0]?.target || 'main');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao consultar entrega.');
    }
  }, [adapter, workspaceId, git?.linked]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { void load(); }, 2500);
    return () => window.clearInterval(timer);
  }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na operação de entrega.');
    } finally {
      setBusy(false);
    }
  }

  function toggle(path: string) {
    setSelected((current) => current.includes(path)
      ? current.filter((item) => item !== path)
      : [...current, path]);
  }

  if (!git?.linked) return null;

  const writable = state?.writable ?? false;
  const files = status?.files ?? [];
  const pr = state?.pullRequests?.[0];

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Entrega da branch</h2>
        <div className="row">
          <Badge tone={writable ? 'success' : 'warning'}>
            {state === null
              ? 'Vínculo Git não confirmado'
              : writable
                ? 'Worktree disponível'
                : 'Fila executando — escrita bloqueada'}
          </Badge>
          <Badge tone={state?.github.authenticated ? 'success' : 'neutral'}>
            {state?.github.found
              ? (state.github.authenticated ? `gh: ${state.github.host || 'ok'}` : 'gh sem autenticação')
              : 'gh não instalado'}
          </Badge>
        </div>
      </div>
      <div className="panel-body stack">
        <p className="panel-subtle">
          Branch <span className="mono">{state?.branch ?? git.branch}</span> · HEAD{' '}
          <span className="mono">{shortId(state?.head ?? '')}</span>. Commit local funciona sem GitHub;
          PR depende do GitHub CLI autenticado.
        </p>
        {state !== null && !writable && (
          <div className="demo-banner" role="status">
            <ShieldAlert size={16} aria-hidden="true" />
            <span>Status e diff continuam disponíveis. Aguarde a fila terminar para alterar o índice.</span>
          </div>
        )}
        {error && <ErrorState message={error} onRetry={() => { setError(null); void load(); }} />}
        {notice && <p className="panel-subtle">{notice}</p>}

        <Collapsible title={`Selecionar arquivos para commit (${selected.length})`} defaultOpen>
          {files.length === 0 ? (
            <EmptyState title="Sem alterações" hint="Não há arquivos para incluir no commit." />
          ) : (
            <div className="history-list">
              {files.map((file) => (
                <div key={file.path} className="history-item">
                  <div className="spread">
                    <label className="row" style={{ cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selected.includes(file.path)}
                        disabled={!writable || busy}
                        onChange={() => toggle(file.path)}
                      />
                      <strong>{file.path}</strong>
                    </label>
                    <Badge tone={file.conflict ? 'danger' : file.staged ? 'success' : 'info'}>
                      {file.conflict ? 'Conflito' : file.staged ? 'Preparado' : 'Não preparado'}
                    </Badge>
                  </div>
                  {file.staged && file.unstaged && (
                    <small>Atenção: há mudanças preparadas e não preparadas neste arquivo.</small>
                  )}
                  {file.oldPath && <small>Renomeado de {file.oldPath}</small>}
                  <div className="row">
                    <Button small disabled={file.binary} onClick={() => void run(async () => {
                      const result = await adapter.getGitDiff(workspaceId, file.path, true, false);
                      setDiffText({ file: `${file.path} (preparado)`, text: result.text ?? result.reason ?? '' });
                    })}>
                      Diff preparado
                    </Button>
                    <Button small disabled={file.binary} onClick={() => void run(async () => {
                      const result = await adapter.getGitDiff(workspaceId, file.path, false, file.untracked);
                      setDiffText({ file: `${file.path} (atual)`, text: result.text ?? result.reason ?? '' });
                    })}>
                      Diff do conteúdo atual
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {diffText && (
            <div className="stack" style={{ gap: 4, marginTop: 10 }}>
              <span className="field-label">{diffText.file}</span>
              <pre className="console diff-view" tabIndex={0}>{diffText.text}</pre>
            </div>
          )}
        </Collapsible>

        <div className="field">
          <label className="field-label" htmlFor="delivery-message">Mensagem do commit</label>
          <input
            id="delivery-message"
            className="input"
            value={message}
            disabled={!writable || busy}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Descreva as mudanças selecionadas"
          />
        </div>
        <div className="row">
          <Button
            disabled={!writable || busy || selected.length === 0 || !message.trim()}
            onClick={() => void run(async () => {
              const next = await adapter.deliveryPreview(workspaceId, selected, message);
              setPreview(next);
            })}
          >
            Revisar seleção
          </Button>
          <Button
            variant="primary"
            disabled={!writable || busy || !preview || !message.trim()}
            onClick={() => void run(async () => {
              const result = await adapter.deliveryCommit({
                workspaceId, previewId: preview!.previewId, selectedPaths: preview!.selected,
                message,
              });
              setNotice(`Commit confirmado: ${shortId(result.hash)}`);
              setPreview(null);
              setSelected([]);
              setMessage('');
            })}
          >
            <Check size={14} aria-hidden="true" /> Criar commit local
          </Button>
        </div>
        {preview && (
          <div className="pr-card">
            <div className="spread">
              <strong>Prévia confirmada</strong>
              <Badge tone={preview.conflict ? 'danger' : 'success'}>
                {preview.conflict ? 'Requer atenção' : 'Pronta'}
              </Badge>
            </div>
            <p className="panel-subtle">HEAD {shortId(preview.head)} · {preview.selected.length} arquivo(s)</p>
            {preview.stagedOutsideSelection.length > 0 && (
              <p className="panel-subtle">
                Preparados fora da seleção: {preview.stagedOutsideSelection.join(', ')} — resolva antes de continuar.
              </p>
            )}
            <div className="row">
              {preview.selected.map((path) => <Badge key={path} tone="info">{path}</Badge>)}
            </div>
            <Button small onClick={() => void run(async () => {
              setPreview(await adapter.deliveryPreview(workspaceId, selected, message));
            })}>
              Atualizar prévia
            </Button>
          </div>
        )}

        <div className="stack" style={{ gap: 4 }}>
          <span className="field-label">Publicar branch</span>
          <div className="row">
            <select className="select" value={remote} onChange={(event) => setRemote(event.target.value)} aria-label="Remoto de destino">
              {(state?.remotes ?? []).map((item) => (
                <option key={item.name} value={item.name}>{item.name} · {item.url}</option>
              ))}
            </select>
            <Button
              disabled={!writable || busy || !remote}
              onClick={() => void run(async () => {
                const result = await adapter.deliveryPush(workspaceId, remote);
                setNotice(`Publicado em ${remote}${result.observedHead ? ` · ${shortId(String(result.observedHead))}` : ''}`);
              })}
            >
              <Send size={14} aria-hidden="true" /> Publicar
            </Button>
          </div>
          {remote && state?.ahead?.[remote] != null && (
            <p className="panel-subtle">{state.ahead[remote]} commit(s) local(is) ainda não publicado(s).</p>
          )}
        </div>

        <Collapsible title="Pull request" badge={<span className="panel-subtle">rascunho por padrão</span>}>
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label className="field-label" htmlFor="delivery-base">Branch de destino</label>
              <input
                id="delivery-base"
                className="input"
                value={base}
                onChange={(event) => setBase(event.target.value)}
              />
            </div>
            <Button
              disabled={busy || !base}
              onClick={() => void run(async () => {
                const next = await adapter.deliveryPrPreview(workspaceId, base);
                setPrPreview(next);
                setTitle(next.title);
                setBody(next.body);
              })}
            >
              Preparar PR
            </Button>
          </div>
          {prPreview && (
            <>
              <p className="panel-subtle">
                {prPreview.repository || 'repositório local'} · {prPreview.source} → {prPreview.target}
              </p>
              {prPreview.existing && (
                <div className="demo-banner" role="status">
                  <GitCommitHorizontal size={16} aria-hidden="true" />
                  <span>PR ativo encontrado para esta origem e destino; ele será reaproveitado.</span>
                </div>
              )}
              <div className="field">
                <label className="field-label" htmlFor="delivery-pr-title">Título</label>
                <input
                  id="delivery-pr-title"
                  className="input"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="delivery-pr-body">Descrição</label>
                <textarea
                  id="delivery-pr-body"
                  className="textarea"
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                />
              </div>
              <Button
                variant="primary"
                disabled={busy}
                onClick={() => void run(async () => {
                  const result = await adapter.deliveryCreatePr({
                    workspaceId, title, body, base, draft: true,
                  });
                  setNotice(result.existing ? 'PR existente reaproveitado.' : 'PR em rascunho aberto.');
                })}
              >
                <Rocket size={14} aria-hidden="true" /> Abrir PR em rascunho
              </Button>
            </>
          )}
          {pr && (
            <div className="pr-card">
              <div className="spread">
                <strong>{pr.title || `PR #${pr.number ?? ''}`}</strong>
                <StatusBadge status={pr.state} />
              </div>
              <KeyValue label="Repositório"><span className="mono">{pr.repository || '—'}</span></KeyValue>
              <KeyValue label="Origem → destino"><span className="mono">{pr.source} → {pr.target}</span></KeyValue>
              <KeyValue label="Atualizado em">{formatDateTime(pr.lastCheckedAt)}</KeyValue>
              <div className="row">
                {pr.url && (
                  <a className="btn" href={pr.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink size={13} aria-hidden="true" /> Abrir no GitHub
                  </a>
                )}
                <Button small disabled={busy} onClick={() => void run(async () => {
                  const result = await adapter.deliveryRefreshPr(workspaceId);
                  setNotice(result.ok ? 'Estado do PR atualizado.' : 'Não foi possível atualizar o PR.');
                })}>
                  Atualizar
                </Button>
              </div>
            </div>
          )}
        </Collapsible>

        <Collapsible title={`Histórico de entrega (${(state?.commits?.length ?? 0) + (state?.pushes?.length ?? 0)})`}>
          {(state?.commits ?? []).map((item) => (
            <div key={item.id} className="history-item">
              <div className="spread">
                <strong>{item.message || 'Sem mensagem'}</strong>
                <StatusBadge status={item.status} />
              </div>
              <small>{shortId(item.hash)} · {formatDateTime(item.createdAt)}</small>
              {item.error && <small>{item.error}</small>}
            </div>
          ))}
          {(state?.pushes ?? []).map((item) => (
            <div key={item.id} className="history-item">
              <div className="spread">
                <strong>Push em {item.remote}</strong>
                <StatusBadge status={item.status} />
              </div>
              <small>{item.upstream} · {formatDateTime(item.createdAt)}</small>
            </div>
          ))}
        </Collapsible>
      </div>
    </section>
  );
}
