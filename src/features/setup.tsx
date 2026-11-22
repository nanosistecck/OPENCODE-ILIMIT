import { FolderPlus, Plus } from 'lucide-react';
import { useState } from 'react';
import { Button, Collapsible, ErrorState } from '../components/common';
import { useAdapter, useMode, useSnapshot } from '../state/AppContext';

/** Cadastro do projeto e do registro do espaço. A worktree é criada na aba Git. */
export function SetupPanel() {
  const adapter = useAdapter();
  const snapshot = useSnapshot();
  const { mode } = useMode();

  const [projectName, setProjectName] = useState('');
  const [objective, setObjective] = useState('');
  const [baseBranch, setBaseBranch] = useState('main');
  const [selectedProject, setSelectedProject] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [branch, setBranch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (mode !== 'connected') return null;

  const projectId = selectedProject || snapshot.projects[0]?.id || '';
  const workspaces = snapshot.workspaces.filter((item) => item.projectId === projectId);

  async function run(action: () => Promise<unknown>, onDone?: () => void) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no cadastro');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Collapsible title="Cadastrar projeto e espaço" badge={<span className="panel-subtle">registro</span>}>
      {error && <ErrorState message={error} onRetry={() => setError(null)} />}
      <div className="setup-grid">
        <div className="stack">
          <strong style={{ fontSize: '0.8rem' }}>Novo projeto</strong>
          <div className="field">
            <label className="field-label" htmlFor="setup-project-name">Nome</label>
            <input
              id="setup-project-name"
              className="input"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="Ex.: NIA"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="setup-objective">Objetivo</label>
            <input
              id="setup-objective"
              className="input"
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Descrição curta"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="setup-base">Branch-base sugerida</label>
            <input
              id="setup-base"
              className="input"
              value={baseBranch}
              onChange={(event) => setBaseBranch(event.target.value)}
            />
          </div>
          <Button
            variant="primary"
            disabled={busy || !projectName.trim()}
            onClick={() => void run(
              async () => {
                const created = await adapter.createProject({
                  name: projectName.trim(),
                  objective: objective.trim(),
                  baseBranch: baseBranch.trim() || 'main',
                });
                setSelectedProject(created.id);
              },
              () => { setProjectName(''); setObjective(''); },
            )}
          >
            <Plus size={14} aria-hidden="true" /> Criar projeto
          </Button>
        </div>

        <div className="stack">
          <strong style={{ fontSize: '0.8rem' }}>Novo espaço (registro)</strong>
          <div className="field">
            <label className="field-label" htmlFor="setup-project-select">Projeto</label>
            <select
              id="setup-project-select"
              className="select"
              value={projectId}
              onChange={(event) => setSelectedProject(event.target.value)}
            >
              {snapshot.projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="setup-ws-name">Nome do espaço</label>
            <input
              id="setup-ws-name"
              className="input"
              value={workspaceName}
              onChange={(event) => setWorkspaceName(event.target.value)}
              placeholder="Ex.: Canvas infinito"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="setup-ws-branch">Branch de trabalho</label>
            <input
              id="setup-ws-branch"
              className="input"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              placeholder="feat/minha-branch"
            />
          </div>
          <Button
            disabled={busy || !projectId || !workspaceName.trim() || !branch.trim()}
            onClick={() => void run(
              () => adapter.createWorkspace(projectId, {
                name: workspaceName.trim(),
                branch: branch.trim(),
              }),
              () => { setWorkspaceName(''); setBranch(''); },
            )}
          >
            <FolderPlus size={14} aria-hidden="true" /> Criar espaço
          </Button>
        </div>
      </div>
      <p className="panel-subtle" style={{ marginTop: 10 }}>
        Após criar o espaço, abra a aba <strong>Git</strong> para vincular o repositório e criar a worktree.
      </p>
      {workspaces.length > 0 && (
        <p className="panel-subtle">Espaços deste projeto: {workspaces.map((item) => item.branch).join(' · ')}</p>
      )}
    </Collapsible>
  );
}
