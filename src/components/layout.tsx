import {
  AlertTriangle,
  Boxes,
  Database,
  FlaskConical,
  Folder,
  FolderSearch,
  GitBranch,
  History,
  ListChecks,
  MessageSquare,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  Play,
  RefreshCw,
  Sun,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useAdapter, useMode, useSnapshot, useTheme } from '../state/AppContext';
import { VIEW_IDS, VIEW_LABELS, type ViewId } from '../domain/navigation';
import { Badge, Button, StatusBadge } from './common';

const VIEW_ICONS: Record<ViewId, typeof MessageSquare> = {
  chat: MessageSquare,
  plan: ListChecks,
  execution: Play,
  git: GitBranch,
  history: History,
};

export interface ChromeProps {
  view: ViewId;
  onViewChange: (view: ViewId) => void;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
  onOpenProject: () => void;
}

export function Sidebar({ inspectorOpen, onToggleInspector, onOpenProject }: Pick<ChromeProps, 'inspectorOpen' | 'onToggleInspector' | 'onOpenProject'>) {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const { theme, toggleTheme } = useTheme();
  const { mode, setMode } = useMode();
  const project = snapshot.projects[0];
  const isDemo = mode === 'demo';
  const disconnected = isDemo
    ? snapshot.connection !== 'connected'
    : snapshot.apiStatus !== 'ok' || snapshot.connection === 'error';

  return (
    <aside className="sidebar" aria-label="Projetos e espaços de trabalho">
      <div className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true">OC</div>
        <div>
          <div className="brand-name">OPENCODE ILIMIT</div>
          <div className="brand-sub">Painel de demonstração</div>
        </div>
      </div>

      <Button block onClick={onOpenProject}>
        <FolderSearch size={14} aria-hidden="true" /> Abrir projeto
      </Button>

      {project && (
        <div className="project-card">
          <div className="sidebar-label" style={{ marginBottom: 6 }}>Projeto</div>
          <h2>{project.name}</h2>
          <p>{project.description}</p>
        </div>
      )}

      <div>
        <div className="sidebar-label" style={{ marginBottom: 8 }}>Espaços de trabalho</div>
        <div className="workspace-list">
          {snapshot.workspaces.map((workspace) => {
            const active = workspace.id === snapshot.activeWorkspaceId;
            return (
              <button
                key={workspace.id}
                type="button"
                className={`workspace-item${active ? ' active' : ''}`}
                aria-current={active ? 'true' : undefined}
                onClick={() => void adapter.setActiveWorkspace(workspace.id)}
              >
                <span className="dot" aria-hidden="true" />
                <span style={{ minWidth: 0 }}>
                  <span className="workspace-name" style={{ display: 'block' }}>{workspace.name}</span>
                  <span className="workspace-branch" style={{ display: 'block' }}>{workspace.branch}</span>
                  <span className="workspace-kind">
                    {workspace.kind === 'base' ? 'base' : 'worktree'} · de {workspace.base}
                  </span>
                  {workspace.workDir && (
                    <span className="workspace-kind mono" style={{ display: 'block', overflowWrap: 'anywhere' }}>
                      <Folder size={10} aria-hidden="true" /> {workspace.workDir} · cadastrado
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-label">Modo de operação</div>
        <div className="mode-switch" role="group" aria-label="Modo de operação">
          <button
            type="button"
            aria-pressed={!isDemo}
            onClick={() => setMode('connected')}
          >
            <Database size={13} aria-hidden="true" /> Conectado
          </button>
          <button
            type="button"
            aria-pressed={isDemo}
            onClick={() => setMode('demo')}
          >
            <FlaskConical size={13} aria-hidden="true" /> Demo
          </button>
        </div>

        <Badge tone={disconnected ? 'danger' : 'success'}>
          {isDemo
            ? (disconnected ? 'Demo · PC desconectado' : 'Demo · PC conectado')
            : (disconnected ? 'API indisponível' : 'API conectada')}
        </Badge>

        <div className="sidebar-footer-row">
          {isDemo && (
            <Button small block onClick={() => void adapter.setConnection(disconnected ? 'connected' : 'disconnected')}>
              {disconnected ? <Wifi size={13} aria-hidden="true" /> : <WifiOff size={13} aria-hidden="true" />}
              {disconnected ? 'Reconectar' : 'Simular queda'}
            </Button>
          )}
          <Button small block onClick={toggleTheme} aria-label={theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'}>
            {theme === 'dark' ? <Sun size={13} aria-hidden="true" /> : <Moon size={13} aria-hidden="true" />}
            {theme === 'dark' ? 'Claro' : 'Escuro'}
          </Button>
        </div>
        <Button small block onClick={onToggleInspector} aria-pressed={inspectorOpen}>
          {inspectorOpen ? <PanelRightClose size={13} aria-hidden="true" /> : <PanelRightOpen size={13} aria-hidden="true" />}
          {inspectorOpen ? 'Ocultar detalhes' : 'Mostrar detalhes'}
        </Button>
      </div>
    </aside>
  );
}

export function Topbar({ view, inspectorOpen, onToggleInspector, onOpenProject }: ChromeProps) {
  const snapshot = useSnapshot();
  const adapter = useAdapter();
  const { mode, setMode } = useMode();
  const workspace = snapshot.workspaces.find((w) => w.id === snapshot.activeWorkspaceId);
  const project = snapshot.projects.find((p) => p.id === workspace?.projectId);
  const isDemo = mode === 'demo';
  const disconnected = isDemo
    ? snapshot.connection !== 'connected'
    : snapshot.apiStatus !== 'ok' || snapshot.connection === 'error';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-context">
          <strong>{project?.name ?? '—'}</strong>
          <span>{workspace?.branch ?? '—'}</span>
        </div>
        <div className="mobile-context">
          <label className="sr-only" htmlFor="workspace-mobile">Espaço de trabalho</label>
          <select
            id="workspace-mobile"
            className="select"
            value={snapshot.activeWorkspaceId}
            onChange={(event) => void adapter.setActiveWorkspace(event.target.value)}
          >
            {snapshot.workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
            ))}
          </select>
          <span>{workspace?.branch}</span>
        </div>
      </div>
      <div className="topbar-right">
        <button
          type="button"
          className="icon-btn"
          onClick={onOpenProject}
          aria-label="Abrir projeto"
          title="Abrir projeto"
        >
          <FolderSearch size={15} aria-hidden="true" />
        </button>
        <span className="badge" aria-label={`Seção atual: ${VIEW_LABELS[view]}`}>{VIEW_LABELS[view]}</span>
        <span className="badge">{isDemo ? 'Demonstração' : 'Conectado'}</span>
        {isDemo ? (
          <StatusBadge status={snapshot.connection} />
        ) : (
          <Badge tone={snapshot.apiStatus === 'ok' ? 'success' : snapshot.apiStatus === 'error' ? 'danger' : 'warning'}>
            {snapshot.apiStatus === 'ok' ? 'API ok' : snapshot.apiStatus === 'error' ? 'API falhou' : 'API verificando'}
          </Badge>
        )}
        <button
          type="button"
          className="icon-btn"
          onClick={() => setMode(isDemo ? 'connected' : 'demo')}
          aria-label={isDemo ? 'Usar modo conectado' : 'Usar modo demonstração'}
          title={isDemo ? 'Usar modo conectado' : 'Usar modo demonstração'}
        >
          {isDemo ? <FlaskConical size={15} aria-hidden="true" /> : <Database size={15} aria-hidden="true" />}
        </button>
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleInspector}
          aria-label={inspectorOpen ? 'Ocultar painel de detalhes' : 'Mostrar painel de detalhes'}
          aria-pressed={inspectorOpen}
        >
          {inspectorOpen ? <PanelRightClose size={15} aria-hidden="true" /> : <PanelRightOpen size={15} aria-hidden="true" />}
        </button>
      </div>
      {disconnected && <span className="sr-only" role="status">Ações que dependem do PC estão desabilitadas.</span>}
    </header>
  );
}

export function MobileNav({ view, onViewChange }: Pick<ChromeProps, 'view' | 'onViewChange'>) {
  return (
    <nav className="mobile-nav" aria-label="Navegação principal">
      {VIEW_IDS.map((id) => {
        const Icon = VIEW_ICONS[id];
        return (
          <button
            key={id}
            type="button"
            className={view === id ? 'active' : ''}
            aria-current={view === id ? 'page' : undefined}
            onClick={() => onViewChange(id)}
          >
            <Icon size={18} aria-hidden="true" />
            {VIEW_LABELS[id]}
          </button>
        );
      })}
    </nav>
  );
}

export function Inspector() {
  const snapshot = useSnapshot();
  const workspace = snapshot.workspaces.find((w) => w.id === snapshot.activeWorkspaceId);
  const git = workspace && snapshot.gitByWorkspace[workspace.id];
  const batches = snapshot.batchesByWorkspace[snapshot.activeWorkspaceId] ?? [];
  const recentEvents = snapshot.events.slice(-6).reverse();

  return (
    <aside className="inspector" aria-label="Detalhes do espaço ativo">
      <div className="row" style={{ marginBottom: 8 }}>
        <Boxes size={16} aria-hidden="true" />
        <h2>Contexto do espaço</h2>
      </div>
      <div className="inspector-row"><span>Espaço</span>{workspace?.name ?? '—'}</div>
      <div className="inspector-row"><span>ID do espaço</span><span className="mono">{workspace?.id ?? '—'}</span></div>
      <div className="inspector-row"><span>Branch (exibição)</span><span className="mono">{git?.branch ?? '—'}</span></div>
      <div className="inspector-row"><span>Base</span><span className="mono">{git?.base ?? '—'}</span></div>
      <div className="inspector-row"><span>Lotes no espaço</span>{batches.length}</div>
      <div className="inspector-row"><span>Eventos recebidos</span>{snapshot.events.length}</div>

      <h2 style={{ marginTop: 20 }}>Eventos recentes</h2>
      {recentEvents.length === 0 ? (
        <p className="panel-subtle">Nenhum evento ainda.</p>
      ) : (
        <div>
          {recentEvents.map((event) => (
            <div key={event.id} className="event-line">
              #{event.sequence} {event.type}
            </div>
          ))}
        </div>
      )}
      <p className="panel-subtle" style={{ marginTop: 14 }}>
        O número de sequência é atribuído pelo backend na integração real.
      </p>
    </aside>
  );
}

/** Falha da API aparece como falha; os dados simulados só entram ao escolher Demo. */
export function ConnectionBanner() {
  const { mode, setMode } = useMode();
  const adapter = useAdapter();
  const snapshot = useSnapshot();

  if (mode !== 'connected' || snapshot.apiStatus !== 'error') return null;

  return (
    <div className="demo-banner error-banner" role="alert">
      <AlertTriangle size={16} aria-hidden="true" />
      <span>
        API indisponível — os dados persistidos não puderam ser carregados.
        O modo demonstração continua disponível.
      </span>
      <div className="row">
        <Button small onClick={() => void adapter.refresh().catch(() => undefined)}>
          <RefreshCw size={13} aria-hidden="true" /> Tentar novamente
        </Button>
        <Button small onClick={() => setMode('demo')}>Usar demonstração</Button>
      </div>
    </div>
  );
}
