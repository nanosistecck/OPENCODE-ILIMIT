import { useEffect, useState } from 'react';
import { EmptyState } from './components/common';
import { ConnectionBanner, Inspector, MobileNav, Sidebar, Topbar } from './components/layout';
import { useAdapter, useMode, useSnapshot } from './state/AppContext';
import { RemoteBanner } from './remote/RemoteBanner';
import { RemoteProvider } from './remote/RemoteProvider';
import { SetupPanel } from './features/setup';
import { OpenProjectDialog } from './features/openProject';
import { VIEW_LABELS, type ViewId } from './domain/navigation';
import { ChatView } from './features/chat';
import { ExecutionView } from './features/execution';
import { GitView } from './features/git';
import { HistoryView } from './features/history';
import { PlanView } from './features/plan';

export default function App() {
  return <RemoteProvider><AppShell /></RemoteProvider>;
}

function AppShell() {
  const [view, setView] = useState<ViewId>('chat');
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [openProject, setOpenProject] = useState(false);
  const snapshot = useSnapshot();
  const adapter = useAdapter();
  const { mode } = useMode();
  const noWorkspace = mode === 'connected'
    && snapshot.apiStatus === 'ok'
    && snapshot.workspaces.length === 0;

  useEffect(() => {
    document.title = `${VIEW_LABELS[view]} · OPENCODE ILIMIT`;
    window.scrollTo({ top: 0 });
  }, [view]);

  useEffect(() => {
    const sync = () => { void adapter.refresh().catch(() => undefined); };
    window.addEventListener('oc-remote-change', sync);
    return () => window.removeEventListener('oc-remote-change', sync);
  }, [adapter]);

  return (
    <div className={`app-shell${inspectorOpen ? ' inspector-open' : ''}`}>
      <Sidebar
        inspectorOpen={inspectorOpen}
        onToggleInspector={() => setInspectorOpen((value) => !value)}
        onOpenProject={() => setOpenProject(true)}
      />
      <div className="main-column">
        <Topbar
          view={view}
          onViewChange={setView}
          inspectorOpen={inspectorOpen}
          onToggleInspector={() => setInspectorOpen((value) => !value)}
          onOpenProject={() => setOpenProject(true)}
        />
        <main className="view-content" id="conteudo" tabIndex={-1}>
          <ConnectionBanner />
          <RemoteBanner />
          <SetupPanel />
          {noWorkspace ? (
            <EmptyState
              title="Nenhum espaço cadastrado"
              hint={'Abra "Cadastrar projeto e espaços de trabalho" acima para começar.'}
            />
          ) : (
            <>
              {view === 'chat' && <ChatView />}
              {view === 'plan' && <PlanView onNavigate={setView} />}
              {view === 'execution' && <ExecutionView onNavigate={setView} />}
              {view === 'git' && <GitView />}
              {view === 'history' && <HistoryView />}
            </>
          )}
        </main>
      </div>
      {inspectorOpen && <Inspector />}
      <MobileNav view={view} onViewChange={setView} />
      {openProject && <OpenProjectDialog onClose={() => setOpenProject(false)} onNavigate={setView} />}
    </div>
  );
}
