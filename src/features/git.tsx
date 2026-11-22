import {
  AlertTriangle, Check, FileDiff, FolderGit2, GitBranch, RefreshCw, Server,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  Badge, Button, DemoNote, EmptyState, ErrorState, KeyValue, LoadingState, StatusBadge,
} from '../components/common';
import { AdapterError } from '../data/adapter';
import { useAdapter, useMode, useSnapshot } from '../state/AppContext';
import { useWorkspaceResource } from '../state/useWorkspaceResource';
import { DeliveryPanel } from './delivery';
import type {
  GitDiffResult, GitInfo, GitOverview, GitStatus, WorkspaceVerification,
} from '../domain/types';
import { shortId } from '../utils/format';

export function GitView() {
  const snapshot = useSnapshot();
  const { mode } = useMode();
  const { loading, error } = useWorkspaceResource();
  const git = snapshot.gitByWorkspace[snapshot.activeWorkspaceId];

  if (loading) return <LoadingState label="Carregando informações Git…" />;
  if (error) return <ErrorState message={error} />;
  if (!git) return <EmptyState title="Sem dados Git neste espaço" />;

  if (mode === 'demo') return <DemoGitView git={git} />;

  const project = snapshot.projects.find((item) => item.workspaceIds.includes(git.workspaceId));
  return <LocalGitView git={git} projectId={project?.id ?? ''} />;
}

/* ------------------------------------------------------------- modo demo */

function DemoGitView({ git }: { git: GitInfo }) {
  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Git</h1>
          <p>Dados ilustrativos do espaço {git.workspaceId}.</p>
        </div>
        <Badge tone="warning">Demonstração</Badge>
      </div>
      <DemoNote>
        Branch, diff, commits e pull request são fictícios. Commit, publicação e abertura de PR ficam reservados
        para a integração real com o PC.
      </DemoNote>
      <div className="view-grid">
        <div className="stack">
          <section className="panel">
            <div className="panel-header"><h2>Branch e base</h2><GitBranch size={15} aria-hidden="true" /></div>
            <div className="panel-body stack">
              <KeyValue label="Branch atual"><span className="mono">{git.branch}</span></KeyValue>
              <KeyValue label="Branch base"><span className="mono">{git.base}</span></KeyValue>
              <KeyValue label="Espaço (vínculo)"><span className="mono">{git.workspaceId}</span></KeyValue>
              <StatusBadge status="success">Simulação identificada</StatusBadge>
            </div>
          </section>
          <section className="panel">
            <div className="panel-header"><h2>Diff de exemplo</h2><span className="panel-subtle">{git.diff.length} linha(s)</span></div>
            <div className="panel-body">
              <div className="diff" role="region" aria-label="Diff de exemplo" tabIndex={0}>
                {git.diff.map((line, index) => (
                  <div key={`${index}-${line.content}`} className={`diff-line diff-line--${line.kind}`}>
                    {line.content || ' '}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
        <div className="stack">
          <section className="panel">
            <div className="panel-header"><h2>Pull request de exemplo</h2></div>
            <div className="panel-body">
              <div className="pr-card">
                <div className="spread">
                  <strong style={{ fontSize: '0.84rem' }}>{git.pullRequest.title}</strong>
                  <StatusBadge status={git.pullRequest.status} />
                </div>
                <div className="stack" style={{ marginTop: 8, gap: 4 }}>
                  <KeyValue label="Origem"><span className="mono">{git.pullRequest.source}</span></KeyValue>
                  <KeyValue label="Destino"><span className="mono">{git.pullRequest.target}</span></KeyValue>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------- modo conectado */

function LocalGitView({ git, projectId }: { git: GitInfo; projectId: string }) {
  const adapter = useAdapter();
  const workspaceId = git.workspaceId;
  const [overview, setOverview] = useState<GitOverview | null>(null);
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [verification, setVerification] = useState<WorkspaceVerification | null>(null);
  const [repoPath, setRepoPath] = useState('');
  const [branchName, setBranchName] = useState('');
  const [startRef, setStartRef] = useState('');
  const [linkPath, setLinkPath] = useState('');
  const [sourceRef, setSourceRef] = useState('');
  const [selected, setSelected] = useState<{ file: string; staged: boolean; untracked: boolean } | null>(null);
  const [diff, setDiff] = useState<GitDiffResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<{ path: string; branch: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    if (!git.linked || !projectId) return;
    const [nextOverview, nextStatus, nextVerification] = await Promise.all([
      adapter.getGitOverview(projectId),
      adapter.getGitStatus(workspaceId),
      adapter.verifyWorkspace(workspaceId),
    ]);
    setOverview(nextOverview);
    setStatus(nextStatus);
    setVerification(nextVerification);
    if (!startRef) {
      setStartRef(nextOverview.refs.suggestions[0]?.options[0]?.ref
        ?? nextOverview.refs.local[0]?.ref
        ?? nextOverview.refs.remote[0]?.ref
        ?? '');
      setSourceRef(nextOverview.refs.remote[0]?.ref ?? '');
    }
  }

  useEffect(() => {
    let active = true;
    if (git.linked && projectId) {
      void reload().catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Falha ao consultar Git.');
      });
    }
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adapter, git.linked, projectId, workspaceId]);

  function message(err: unknown) {
    return err instanceof Error ? err.message : 'Falha na operação Git.';
  }

  function captureRecovery(err: unknown) {
    if (err instanceof AdapterError && err.detail?.worktreeCreated) {
      setRecovery({
        path: String(err.detail.path ?? ''),
        branch: String(err.detail.branch ?? branchName),
      });
    }
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(message(err));
      captureRecovery(err);
    } finally {
      setBusy(false);
    }
  }

  async function showDiff(file: string, staged: boolean, untracked: boolean) {
    await run(async () => {
      setSelected({ file, staged, untracked });
      setDiff(await adapter.getGitDiff(workspaceId, file, staged, untracked));
    });
  }

  const summary = status?.summary ?? git.summary ?? { total: 0, staged: 0, unstaged: 0, untracked: 0, conflicts: 0 };
  const reasons = verification?.reasons ?? git.verification?.reasons ?? [];
  const allRefs = overview
    ? [
        ...overview.refs.local.map((ref) => ({ value: ref.ref, label: `local · ${ref.name} · ${shortId(ref.commit)}` })),
        ...overview.refs.remote.map((ref) => ({ value: ref.ref, label: `remoto · ${ref.name} · ${shortId(ref.commit)}` })),
      ]
    : [];

  return (
    <div className="stack">
      <div className="view-header">
        <div>
          <h1>Git</h1>
          <p>Espaço {workspaceId} · repositório local verificado pelo backend.</p>
        </div>
        <div className="row">
          {git.linked ? <Badge tone="success">Git vinculado</Badge> : <Badge tone="warning">Vínculo pendente</Badge>}
          <Button
            small
            disabled={busy || !git.linked}
            onClick={() => void run(async () => {
              setStatus(await adapter.getGitStatus(workspaceId, true));
              setVerification(await adapter.verifyWorkspace(workspaceId));
            })}
          >
            <RefreshCw size={13} aria-hidden="true" /> Atualizar Git
          </Button>
        </div>
      </div>

      <p className="panel-subtle">
        <Server size={13} aria-hidden="true" /> O caminho informado pertence ao computador que executa o backend,
        inclusive quando o painel é aberto pelo celular.
      </p>

      {error && <ErrorState message={error} onRetry={() => { setError(null); void reload().catch(() => undefined); }} />}

      {recovery && (
        <div className="demo-banner" role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>
            A worktree foi criada em <span className="mono">{recovery.path}</span>, mas o banco falhou.
            Vincule a pasta existente — nenhum arquivo será apagado.
          </span>
          <Button
            small
            variant="primary"
            onClick={() => void run(async () => {
              setStatus(await adapter.openGitWorkspace(workspaceId, {
                action: 'link', path: recovery.path, branch: recovery.branch,
              }));
              setRecovery(null);
              await reload();
            })}
          >
            Vincular worktree existente
          </Button>
        </div>
      )}

      <div className="view-grid">
        <div className="stack">
          <section className="panel">
            <div className="panel-header"><h2>Repositório</h2><FolderGit2 size={15} aria-hidden="true" /></div>
            <div className="panel-body stack">
              {!git.linked ? (
                <>
                  <div className="field">
                    <label className="field-label" htmlFor="git-repo-path">Caminho do repositório neste computador</label>
                    <input
                      id="git-repo-path"
                      className="input"
                      placeholder="C:\repos\nia"
                      value={repoPath}
                      onChange={(event) => setRepoPath(event.target.value)}
                    />
                  </div>
                  <Button
                    variant="primary"
                    disabled={busy || !repoPath.trim()}
                    onClick={() => void run(async () => {
                      setOverview(await adapter.linkRepository(projectId, repoPath.trim()));
                      await adapter.refresh();
                      await reload();
                    })}
                  >
                    Verificar e vincular repositório
                  </Button>
                  <p className="panel-subtle">
                    Uma subpasta válida é resolvida para a raiz. Worktrees compartilham o mesmo repositório.
                  </p>
                </>
              ) : (
                <>
                  <KeyValue label="Raiz"><span className="mono">{git.repoRoot || overview?.root || '—'}</span></KeyValue>
                  <KeyValue label="Repositório comum"><span className="mono">{shortId(overview?.commonDir ?? '')}</span></KeyValue>
                  <KeyValue label="Branch original"><span className="mono">{overview?.state.branch ?? git.branch}</span></KeyValue>
                  <KeyValue label="Commit original"><span className="mono">{shortId(overview?.state.head ?? '')}</span></KeyValue>
                  <StatusBadge status={git.gitStatus === 'ready' ? 'success' : 'warning'}>
                    {git.gitStatus === 'ready' ? 'Worktree verificada' : 'Vínculo pendente'}
                  </StatusBadge>
                </>
              )}
            </div>
          </section>

          {git.linked && overview && (
            <section className="panel">
              <div className="panel-header"><h2>Base e branches</h2><GitBranch size={15} aria-hidden="true" /></div>
              <div className="panel-body stack">
                <div className="stack" style={{ gap: 4 }}>
                  <span className="field-label">Bases sugeridas (referência exata)</span>
                  {overview.refs.suggestions.map((suggestion) => (
                    <div key={suggestion.name} className="pr-card">
                      <strong style={{ fontSize: '0.8rem' }}>{suggestion.name}</strong>
                      {suggestion.options.length > 1 && (
                        <p className="panel-subtle">
                          Local e remoto apontam para commits diferentes — escolha explicitamente abaixo.
                        </p>
                      )}
                      {suggestion.options.map((option) => (
                        <div key={option.ref} className="verification">
                          <span>{option.label ?? option.name}</span>
                          <span className="mono">{shortId(option.commit)}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                  {!overview.refs.suggestions.length && (
                    <p className="panel-subtle">Nenhuma base com commit disponível localmente.</p>
                  )}
                </div>

                <div className="field">
                  <label className="field-label" htmlFor="git-branch-name">Nome da nova branch</label>
                  <input
                    id="git-branch-name"
                    className="input"
                    placeholder="feat/minha-branch"
                    value={branchName}
                    onChange={(event) => setBranchName(event.target.value)}
                  />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="git-start-ref">Referência de partida</label>
                  <select
                    id="git-start-ref"
                    className="select"
                    value={startRef}
                    onChange={(event) => setStartRef(event.target.value)}
                  >
                    {allRefs.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
                <div className="row">
                  <Button
                    variant="primary"
                    disabled={busy || !branchName.trim() || !startRef}
                    onClick={() => void run(async () => {
                      setRecovery(null);
                      setStatus(await adapter.createGitWorkspace(workspaceId, branchName.trim(), startRef));
                      await reload();
                    })}
                  >
                    Criar branch e worktree
                  </Button>
                </div>

                <div className="stack" style={{ gap: 4, marginTop: 8 }}>
                  <span className="field-label">Abrir branch existente</span>
                  <div className="field">
                    <label className="field-label" htmlFor="git-link-path">Vincular pasta existente</label>
                    <div className="row">
                      <input
                        id="git-link-path"
                        className="input"
                        placeholder="C:\worktrees\minha-branch"
                        value={linkPath}
                        onChange={(event) => setLinkPath(event.target.value)}
                      />
                      <Button
                        disabled={busy || !linkPath.trim()}
                        onClick={() => void run(async () => {
                          setStatus(await adapter.openGitWorkspace(workspaceId, {
                            action: 'link', path: linkPath.trim(),
                          }));
                          await reload();
                        })}
                      >
                        Vincular
                      </Button>
                    </div>
                  </div>
                  <div className="row">
                    <Button
                      disabled={busy}
                      onClick={() => void run(async () => {
                        setStatus(await adapter.openGitWorkspace(workspaceId, { action: 'attach' }));
                        await reload();
                      })}
                    >
                      Criar worktree para branch local
                    </Button>
                    <Button
                      disabled={busy || !sourceRef}
                      onClick={() => void run(async () => {
                        setStatus(await adapter.openGitWorkspace(workspaceId, {
                          action: 'remote', sourceRef,
                        }));
                        await reload();
                      })}
                    >
                      Criar branch local a partir do remoto
                    </Button>
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="git-source-ref">Referência remota de origem</label>
                    <select
                      id="git-source-ref"
                      className="select"
                      value={sourceRef}
                      onChange={(event) => setSourceRef(event.target.value)}
                    >
                      {overview.refs.remote.map((option) => (
                        <option key={option.ref} value={option.ref}>{option.name} · {shortId(option.commit)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>

        <div className="stack">
          <section className="panel">
            <div className="panel-header">
              <h2>Estado do espaço</h2>
              {git.linked && <Badge tone={verification?.ready ? 'success' : 'warning'}>
                {verification?.ready ? 'Apto' : 'Verificar'}
              </Badge>}
            </div>
            <div className="panel-body stack">
              <KeyValue label="Branch"><span className="mono">{status?.branch || git.branch}</span></KeyValue>
              <KeyValue label="Base"><span className="mono">{git.base}</span></KeyValue>
              <KeyValue label="Pasta de trabalho"><span className="mono">{status?.path || git.workDir || '—'}</span></KeyValue>
              <KeyValue label="HEAD atual"><span className="mono">{status?.head || git.head || '—'}</span></KeyValue>
              <KeyValue label="HEAD no vínculo"><span className="mono">{shortId(verification?.boundHead ?? '')}</span></KeyValue>
              <div className="row">
                <Badge tone="info">{summary.staged} preparado(s)</Badge>
                <Badge tone="warning">{summary.unstaged} não preparado(s)</Badge>
                <Badge tone="neutral">{summary.untracked} novo(s)</Badge>
                <Badge tone={summary.conflicts ? 'danger' : 'neutral'}>{summary.conflicts} conflito(s)</Badge>
              </div>
              {status?.operations?.length ? (
                <p className="panel-subtle">Operação em andamento: {status.operations.join(', ')}</p>
              ) : null}
              {reasons.length > 0 && (
                <div className="reason-list">
                  {reasons.map((reason) => (
                    <div key={reason} className="badge badge--danger badge--dot">{reason}</div>
                  ))}
                </div>
              )}
              {!git.linked && <EmptyState title="Repositório não vinculado" hint="Informe o caminho acima para verificar o Git." />}
              {git.linked && status?.available === false && (
                <p className="panel-subtle">{status.reason}: a última leitura ficou preservada.</p>
              )}
            </div>
          </section>

          {git.linked && (
            <section className="panel">
              <div className="panel-header">
                <h2>Arquivos alterados</h2>
                <span className="panel-subtle">{summary.total} arquivo(s)</span>
              </div>
              <div className="panel-body tight">
                {!status?.files?.length ? (
                  <EmptyState title="Sem alterações" hint="Arquivos preparados e não preparados aparecem aqui." />
                ) : (
                  <div className="history-list">
                    {status.files.map((file) => (
                      <div key={file.path} className="history-item">
                        <div className="spread">
                          <strong className="row"><FileDiff size={13} aria-hidden="true" /> {file.path}</strong>
                          <Badge tone={file.conflict ? 'danger' : file.untracked ? 'warning' : file.staged ? 'success' : 'info'}>
                            {file.conflict ? 'Conflito' : file.untracked ? 'Novo' : file.staged ? 'Preparado' : 'Não preparado'}
                          </Badge>
                        </div>
                        <small>
                          {file.oldPath ? `renomeado de ${file.oldPath} · ` : ''}
                          índice: {file.indexStatus} · árvore: {file.worktreeStatus}
                          {file.binary ? ' · binário' : ''}
                        </small>
                        <div className="row">
                          <Button small disabled={file.binary} onClick={() => void showDiff(file.path, true, false)}>
                            Diff preparado
                          </Button>
                          <Button small disabled={file.binary} onClick={() => void showDiff(file.path, false, file.untracked)}>
                            {file.untracked ? 'Prévia do arquivo' : 'Diff não preparado'}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {git.linked && selected && (
            <section className="panel">
              <div className="panel-header">
                <h2>{selected.file}</h2>
                <Badge tone={selected.staged ? 'success' : 'info'}>
                  {selected.staged ? 'Preparado' : selected.untracked ? 'Novo' : 'Não preparado'}
                </Badge>
              </div>
              <div className="panel-body">
                {!diff ? (
                  <LoadingState label="Lendo diff…" />
                ) : !diff.available ? (
                  <EmptyState title="Prévia indisponível" hint={diff.reason} />
                ) : (
                  <>
                    <pre className="console diff-view" tabIndex={0}>{diff.text}</pre>
                    {diff.truncated && (
                      <p className="panel-subtle">Prévia truncada — o arquivo é maior que o limite configurado.</p>
                    )}
                  </>
                )}
              </div>
            </section>
          )}

          {git.linked && (
            <p className="panel-subtle">
              <Check size={12} aria-hidden="true" /> A verificação acima é a operação que o motor de fila usa.
            </p>
          )}
        </div>
      </div>

      <DeliveryPanel />
    </div>
  );
}
