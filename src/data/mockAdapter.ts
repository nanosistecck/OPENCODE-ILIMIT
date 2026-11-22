import { AdapterError, type ExtendedAdapter } from './adapter';
import { createInitialSnapshot } from './fixtures';
import type {
  AppEvent,
  AppSnapshot,
  Attempt,
  Batch,
  ConnectionState,
  EventContext,
  EventType,
  ID,
  NewQueueItem,
  WorkspaceState,
  NewProjectInput,
  NewWorkspaceInput,
  PlanInput,
  Conversation,
  GitOverview,
  GitStatus,
  GitDiffResult,
  RepoProbe,
  WorkspaceVerification,
  GitOpenInput,
  QueueBatch,
  QueueState,
  LogChunk,
  OpenCodeStatus,
  OpenCodeConfigInput,
  ChatState,
  ProjectAnalysis,
  PlanProposal,
  ReviewReport,
  Plan,
  DeliveryState,
  DeliveryPreview,
  DeliveryPrPreview,
  DeliveryCreatePrInput,
  RemoteStatus,
  AppEventEnvelope,
  DiscoveryPreview,
  DiscoveryOpenResult,
  DiscoveryPreferenceRecord,
} from '../domain/types';

const STEP_MS = 750;
const IO_MS = 90;

type Timer = ReturnType<typeof setTimeout>;

function delay(ms = IO_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function now(): string {
  return new Date().toISOString();
}

/**
 * Adaptador de demonstração. Toda mutação gera um novo snapshot imutável e
 * um evento com sequência, reproduzindo o contrato que o backend enviará.
 */
export class MockAdapter implements ExtendedAdapter {
  private snapshot: AppSnapshot = createInitialSnapshot();
  private listeners = new Set<() => void>();
  private sequence = 0;
  private timers = new Map<ID, Timer>();
  private idCounter = 0;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): AppSnapshot => this.snapshot;

  private nextId(prefix: string): string {
    this.idCounter += 1;
    return `${prefix}-${Date.now().toString(36)}-${this.idCounter}`;
  }

  private makeEvent(type: EventType, context: EventContext, summary: string): AppEvent {
    this.sequence += 1;
    return {
      sequence: this.sequence,
      id: this.nextId('evt'),
      type,
      context,
      createdAt: now(),
      summary,
    };
  }

  private update(mutator: (draft: AppSnapshot) => void, event?: [EventType, EventContext, string]): void {
    const draft = structuredClone(this.snapshot);
    mutator(draft);
    if (event) draft.events = [...draft.events, this.makeEvent(...event)];
    this.snapshot = draft;
    for (const listener of [...this.listeners]) listener();
  }

  private assertConnected(): void {
    if (this.snapshot.connection !== 'connected') {
      throw new AdapterError('Ação indisponível: PC desconectado.', 'DISCONNECTED');
    }
  }

  private getBatch(batchId: ID): Batch {
    for (const list of Object.values(this.snapshot.batchesByWorkspace)) {
      const found = list.find((batch) => batch.id === batchId);
      if (found) return found;
    }
    throw new AdapterError('Lote não encontrado.', 'NOT_FOUND');
  }

  private getBatchWorkspace(batchId: ID): ID {
    for (const [workspaceId, list] of Object.entries(this.snapshot.batchesByWorkspace)) {
      if (list.some((batch) => batch.id === batchId)) return workspaceId;
    }
    throw new AdapterError('Lote não encontrado.', 'NOT_FOUND');
  }

  private clearTimer(batchId: ID): void {
    const timer = this.timers.get(batchId);
    if (timer) clearTimeout(timer);
    this.timers.delete(batchId);
  }

  // ---------------------------------------------------------------- consultas

  async listProjects() {
    await delay();
    return structuredClone(this.snapshot.projects);
  }

  async listWorkspaces(projectId: ID) {
    await delay();
    return structuredClone(this.snapshot.workspaces.filter((w) => w.projectId === projectId));
  }

  async getWorkspaceState(workspaceId: ID): Promise<WorkspaceState> {
    await delay();
    const workspace = this.snapshot.workspaces.find((w) => w.id === workspaceId);
    const project = workspace && this.snapshot.projects.find((p) => p.id === workspace.projectId);
    if (!workspace || !project) throw new AdapterError('Espaço não encontrado.', 'NOT_FOUND');
    return structuredClone({
      workspace,
      project,
      conversation: this.snapshot.conversationsByWorkspace[workspaceId],
      plan: this.snapshot.plansByWorkspace[workspaceId],
      batch: this.snapshot.batchesByWorkspace[workspaceId]?.[0] ?? null,
      git: this.snapshot.gitByWorkspace[workspaceId],
      connection: this.snapshot.connection,
    });
  }

  async setActiveWorkspace(workspaceId: ID): Promise<void> {
    if (!this.snapshot.workspaces.some((w) => w.id === workspaceId)) {
      throw new AdapterError('Espaço não encontrado.', 'NOT_FOUND');
    }
    const project = this.snapshot.workspaces.find((w) => w.id === workspaceId)!.projectId;
    this.update(
      (draft) => { draft.activeWorkspaceId = workspaceId; },
      ['workspace.changed', { workspaceId, projectId: project }, 'Espaço ativo alterado'],
    );
  }

  async listBatches(workspaceId: ID): Promise<Batch[]> {
    await delay();
    return structuredClone(this.snapshot.batchesByWorkspace[workspaceId] ?? []);
  }

  async listAttempts(workspaceId: ID): Promise<Attempt[]> {
    await delay();
    return structuredClone(this.snapshot.attemptsByWorkspace[workspaceId] ?? []);
  }

  async listEvents(): Promise<AppEvent[]> {
    await delay();
    return structuredClone(this.snapshot.events);
  }

  // ---------------------------------------------------------------- chat/plano

  async sendMessage(workspaceId: ID, conversationId: ID, content: string): Promise<void> {
    this.assertConnected();
    const text = content.trim();
    if (!text) throw new AdapterError('Mensagem vazia.', 'INVALID_STATE');
    const messageId = this.nextId('msg');
    this.update(
      (draft) => {
        const conversation = draft.conversationsByWorkspace[workspaceId];
        conversation.messages.push({
          id: messageId, conversationId, role: 'user', content: text,
          createdAt: now(), status: 'sending',
        });
      },
      ['message.created', { workspaceId, conversationId }, 'Mensagem enviada (pendente)'],
    );
    await delay(320);
    this.update(
      (draft) => {
        const conversation = draft.conversationsByWorkspace[workspaceId];
        const message = conversation.messages.find((m) => m.id === messageId);
        if (message) message.status = 'sent';
        conversation.messages.push({
          id: this.nextId('msg'), conversationId, role: 'assistant',
          content: 'Recebido (modo demonstração). Esta resposta será gerada pelo OpenCode na integração real.',
          createdAt: now(), status: 'sent',
        });
      },
      ['message.created', { workspaceId, conversationId }, 'Resposta do agente recebida'],
    );
  }

  async reviewPlan(workspaceId: ID): Promise<void> {
    this.assertConnected();
    await delay();
    this.update(
      (draft) => { draft.plansByWorkspace[workspaceId].status = 'in_review'; },
      ['plan.reviewed', { workspaceId }, 'Plano enviado para revisão'],
    );
  }

  async generateQueue(workspaceId: ID): Promise<Batch> {
    this.assertConnected();
    await delay();
    const plan = this.snapshot.plansByWorkspace[workspaceId];
    const batchId = this.nextId('batch');
    const batch: Batch = {
      id: batchId,
      workspaceId,
      name: `Fila do plano v${plan.version}`,
      createdAt: now(),
      status: 'idle',
      pauseRequested: false,
      cursor: 0,
      items: plan.steps.map((step, index) => ({
        id: this.nextId('item'),
        kind: 'prompt' as const,
        title: step.title,
        content: `${step.description}\n\nCritério de aceite: ${step.acceptanceCriteria}`,
        order: index,
        status: 'pending' as const,
      })),
    };
    this.update(
      (draft) => { draft.batchesByWorkspace[workspaceId] = [batch, ...(draft.batchesByWorkspace[workspaceId] ?? [])]; },
      ['queue.generated', { workspaceId, batchId }, 'Fila simulada gerada a partir do plano'],
    );
    return structuredClone(batch);
  }

  // ---------------------------------------------------------------- fila

  private editBatch(batchId: ID, mutator: (batch: Batch) => void, summary: string): void {
    const workspaceId = this.getBatchWorkspace(batchId);
    this.update(
      (draft) => {
        const batch = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        mutator(batch);
      },
      ['queue.updated', { workspaceId, batchId }, summary],
    );
  }

  private assertEditable(batch: Batch): void {
    if (batch.status === 'running' || batch.status === 'pausing') {
      throw new AdapterError('Fila em execução: pause antes de editar.', 'INVALID_STATE');
    }
  }

  async addQueueItems(batchId: ID, items: NewQueueItem[]): Promise<void> {
    this.assertConnected();
    await delay();
    const batch = this.getBatch(batchId);
    this.assertEditable(batch);
    this.editBatch(batchId, (draft) => {
      for (const item of items) {
        draft.items.push({
          id: this.nextId('item'),
          ...item,
          order: draft.items.length,
          status: 'pending',
        });
      }
    }, `${items.length} item(ns) adicionado(s) à fila`);
  }

  async updateQueueItem(batchId: ID, itemId: ID, patch: Partial<Pick<NewQueueItem, 'title' | 'content'>>): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    this.assertEditable(batch);
    this.editBatch(batchId, (draft) => {
      const item = draft.items.find((i) => i.id === itemId);
      if (!item) throw new AdapterError('Item não encontrado.', 'NOT_FOUND');
      if (patch.title !== undefined) item.title = patch.title;
      if (patch.content !== undefined) item.content = patch.content;
    }, 'Item da fila atualizado');
  }

  async removeQueueItem(batchId: ID, itemId: ID): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    this.assertEditable(batch);
    this.editBatch(batchId, (draft) => {
      const index = draft.items.findIndex((i) => i.id === itemId);
      if (index < 0) throw new AdapterError('Item não encontrado.', 'NOT_FOUND');
      draft.items.splice(index, 1);
      draft.items.forEach((item, i) => { item.order = i; });
      if (index < draft.cursor) draft.cursor = Math.max(0, draft.cursor - 1);
      draft.cursor = Math.min(draft.cursor, draft.items.length);
    }, 'Item removido da fila');
  }

  async moveQueueItem(batchId: ID, itemId: ID, direction: -1 | 1): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    this.assertEditable(batch);
    this.editBatch(batchId, (draft) => {
      const index = draft.items.findIndex((i) => i.id === itemId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= draft.items.length) return;
      [draft.items[index], draft.items[target]] = [draft.items[target], draft.items[index]];
      draft.items.forEach((item, i) => { item.order = i; });
    }, 'Item reordenado');
  }

  // ---------------------------------------------------------------- execução

  private scheduleAdvance(batchId: ID): void {
    this.clearTimer(batchId);
    const timer = setTimeout(() => this.advance(batchId), STEP_MS);
    this.timers.set(batchId, timer);
  }

  private advance(batchId: ID): void {
    this.timers.delete(batchId);
    const batch = this.getBatch(batchId);
    if (batch.status !== 'running' || this.snapshot.connection !== 'connected') return;
    if (batch.cursor >= batch.items.length) {
      this.finishBatch(batchId);
      return;
    }
    const item = batch.items[batch.cursor];
    const workspaceId = batch.workspaceId;
    const attemptId = this.nextId('attempt');
    item.status = 'running';
    const attempt: Attempt = {
      id: attemptId,
      batchId,
      workspaceId,
      itemId: item.id,
      itemTitle: item.title,
      stepIndex: batch.cursor,
      prompt: item.content,
      output: 'Executando etapa…',
      result: '',
      status: 'running',
      branch: this.snapshot.workspaces.find((w) => w.id === workspaceId)?.branch ?? '',
      workspaceRef: workspaceId,
      startedAt: now(),
    };
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.items[target.cursor].status = 'running';
        draft.attemptsByWorkspace[workspaceId] = [attempt, ...(draft.attemptsByWorkspace[workspaceId] ?? [])];
      },
      ['attempt.started', { workspaceId, batchId, attemptId }, `Iniciada: ${item.title}`],
    );
    const timer = setTimeout(() => this.finishStep(batchId, attemptId, item.id), STEP_MS);
    this.timers.set(batchId, timer);
  }

  private finishStep(batchId: ID, attemptId: ID, itemId: ID): void {
    this.timers.delete(batchId);
    const batch = this.getBatch(batchId);
    if (this.snapshot.connection !== 'connected') return;
    const item = batch.items.find((i) => i.id === itemId);
    if (!item) return;
    const shouldFail = /falha simulada|\bFALHA\b/i.test(item.content);
    const index = batch.items.findIndex((i) => i.id === itemId);
    const workspaceId = batch.workspaceId;

    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        const targetItem = target.items.find((i) => i.id === itemId)!;
        targetItem.status = shouldFail ? 'failed' : 'done';
        const attempt = draft.attemptsByWorkspace[workspaceId].find((a) => a.id === attemptId);
        if (attempt) {
          attempt.status = shouldFail ? 'failure' : 'success';
          attempt.output = shouldFail
            ? `[erro] dependência ausente\n[erro] etapa "${targetItem.title}" falhou\n\nDica: edite o prompt removendo "Falha simulada" e retome.`
            : `[ok] ${targetItem.title}\n[ok] saída validada\n[ok] critério de aceite atendido`;
          attempt.result = shouldFail ? 'Falha — etapas seguintes permanecem pendentes.' : 'Sucesso';
          attempt.finishedAt = now();
        }
      },
      ['attempt.finished', { workspaceId, batchId, attemptId }, shouldFail ? `Falha: ${item.title}` : `Concluída: ${item.title}`],
    );

    const current = this.getBatch(batchId);
    if (current.pauseRequested) {
      this.update(
        (draft) => {
          const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
          target.pauseRequested = false;
          target.status = 'paused';
        },
        ['batch.paused.confirmed', { workspaceId, batchId }, 'Pausa confirmada após a etapa atual'],
      );
      return;
    }
    if (shouldFail) {
      // cursor NÃO avança: a etapa failada continua como próxima até retomar/corrigir.
      this.update(
        (draft) => { draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!.status = 'failed'; },
        undefined,
      );
      return;
    }
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.cursor = index + 1;
      },
    );
    const updated = this.getBatch(batchId);
    if (updated.cursor >= updated.items.length) {
      this.finishBatch(batchId);
    } else {
      this.scheduleAdvance(batchId);
    }
  }

  private finishBatch(batchId: ID): void {
    const workspaceId = this.getBatchWorkspace(batchId);
    this.clearTimer(batchId);
    this.update(
      (draft) => { draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!.status = 'completed'; },
      ['batch.completed', { workspaceId, batchId }, 'Lote concluído'],
    );
  }

  async startBatch(batchId: ID): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    if (batch.status !== 'idle' && batch.status !== 'completed') {
      throw new AdapterError('Lote não está pronto para iniciar.', 'INVALID_STATE');
    }
    const workspaceId = batch.workspaceId;
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.cursor = 0;
        target.pauseRequested = false;
        target.status = 'running';
        target.items.forEach((item) => { item.status = 'pending'; });
      },
      ['batch.started', { workspaceId, batchId }, 'Execução iniciada'],
    );
    this.scheduleAdvance(batchId);
  }

  async requestPause(batchId: ID): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    if (batch.status !== 'running') {
      throw new AdapterError('Só é possível pausar durante a execução.', 'INVALID_STATE');
    }
    const workspaceId = batch.workspaceId;
    const hasRunningStep = batch.items.some((item) => item.status === 'running');

    // Solicitada: ainda há uma etapa em execução.
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.pauseRequested = true;
        target.status = hasRunningStep ? 'pausing' : 'paused';
      },
      ['batch.paused.requested', { workspaceId, batchId }, 'Pausa solicitada — aguardando etapa atual'],
    );

    // Sem etapa em execução, a confirmação é imediata (não há o que esperar).
    if (!hasRunningStep) {
      this.clearTimer(batchId);
      this.update(
        (draft) => {
          const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
          target.pauseRequested = false;
          target.status = 'paused';
        },
        ['batch.paused.confirmed', { workspaceId, batchId }, 'Pausa confirmada — nenhuma etapa em execução'],
      );
    }
  }

  async resumeBatch(batchId: ID): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    if (batch.status !== 'paused' && batch.status !== 'failed') {
      throw new AdapterError('Lote não pode ser retomado neste estado.', 'INVALID_STATE');
    }
    const workspaceId = batch.workspaceId;
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.pauseRequested = false;
        target.status = 'running';
        const next = target.items[target.cursor];
        if (next && next.status === 'failed') next.status = 'pending';
      },
      ['batch.resumed', { workspaceId, batchId }, 'Execução retomada'],
    );
    this.scheduleAdvance(batchId);
  }

  async cancelBatch(batchId: ID): Promise<void> {
    this.assertConnected();
    const batch = this.getBatch(batchId);
    if (batch.status !== 'running' && batch.status !== 'pausing') {
      throw new AdapterError('Lote não está em execução.', 'INVALID_STATE');
    }
    this.clearTimer(batchId);
    const workspaceId = batch.workspaceId;
    this.update(
      (draft) => {
        const target = draft.batchesByWorkspace[workspaceId].find((b) => b.id === batchId)!;
        target.pauseRequested = false;
        target.status = 'cancelled';
        target.items.forEach((item) => {
          if (item.status === 'running' || item.status === 'pending') item.status = 'cancelled';
        });
        const attempt = draft.attemptsByWorkspace[workspaceId].find((a) => a.batchId === batchId && a.status === 'running');
        if (attempt) {
          attempt.status = 'cancelled';
          attempt.result = 'Cancelado pelo usuário';
          attempt.output = '[aviso] execução cancelada';
          attempt.finishedAt = now();
        }
      },
      ['batch.cancelled', { workspaceId, batchId }, 'Execução cancelada'],
    );
  }

  // ---------------------------------------------------------------- conexão

  async setConnection(state: ConnectionState): Promise<void> {
    if (state === 'disconnected' || state === 'error') {
      for (const batchId of [...this.timers.keys()]) this.clearTimer(batchId);
    }
    this.update(
      (draft) => {
        draft.connection = state;
        if (state === 'connected') {
          for (const [workspaceId, batches] of Object.entries(draft.batchesByWorkspace)) {
            for (const batch of batches) {
              if (batch.status === 'pausing') {
                batch.pauseRequested = false;
                batch.status = 'paused';
              }
            }
            void workspaceId;
          }
        }
      },
      ['connection.changed', { workspaceId: this.snapshot.activeWorkspaceId }, `Conexão: ${state}`],
    );
    if (state === 'connected') {
      for (const batches of Object.values(this.snapshot.batchesByWorkspace)) {
        for (const batch of batches) {
          if (batch.status === 'running') this.scheduleAdvance(batch.id);
        }
      }
    }
  }

  // --------------------------------------------------- operações de cadastro
  // Implementadas também no demo para que as telas nunca ramifiquem por origem.

  async createProject(input: NewProjectInput) {
    await delay();
    const project = {
      id: this.nextId('prj'),
      name: input.name,
      description: input.objective || '',
      objective: input.objective || '',
      baseBranch: input.baseBranch || 'main',
      workspaceIds: [] as string[],
    };
    this.update((draft) => { draft.projects.push(project); });
    return structuredClone(project);
  }

  async createWorkspace(projectId: ID, input: NewWorkspaceInput) {
    await delay();
    const workspace = {
      id: this.nextId('ws'),
      projectId,
      name: input.name,
      branch: input.branch,
      base: input.baseBranch || 'main',
      kind: (input.kind === 'base' ? 'base' : 'worktree') as 'base' | 'worktree',
      createdAt: now(),
      workDir: input.workDir || '',
    };
    this.update((draft) => {
      draft.workspaces.push(workspace);
      const project = draft.projects.find((item) => item.id === projectId);
      if (project) project.workspaceIds.push(workspace.id);
      draft.conversationsByWorkspace[workspace.id] = {
        id: this.nextId('conv'), workspaceId: workspace.id, title: 'Conversa',
        messages: [], activity: [],
      };
      draft.plansByWorkspace[workspace.id] = {
        id: this.nextId('plan'), workspaceId: workspace.id, objective: '', version: 0,
        status: 'draft', steps: [], versions: [],
      };
      draft.batchesByWorkspace[workspace.id] = [];
      draft.attemptsByWorkspace[workspace.id] = [];
      draft.gitByWorkspace[workspace.id] = {
        workspaceId: workspace.id, branch: workspace.branch, base: workspace.base,
        workDir: workspace.workDir, registeredOnly: true, simulated: true,
        diff: [], commits: [],
        pullRequest: {
          id: 'pr-pending', title: 'Pull request — integração futura',
          source: workspace.branch, target: workspace.base, status: 'draft',
          verifications: [{ id: 'v-pending', name: 'Verificação Git', status: 'pending', conclusion: 'Prompt 03' }],
        },
      };
    });
    return structuredClone(workspace);
  }

  async createConversation(workspaceId: ID): Promise<Conversation> {
    await delay();
    const conversation: Conversation = {
      id: this.nextId('conv'), workspaceId, title: 'Conversa', messages: [], activity: [],
    };
    this.update((draft) => { draft.conversationsByWorkspace[workspaceId] = conversation; });
    return structuredClone(conversation);
  }

  async savePlan(workspaceId: ID, plan: PlanInput): Promise<void> {
    await delay();
    this.update((draft) => {
      const current = draft.plansByWorkspace[workspaceId];
      if (!current) return;
      const version = current.version + 1;
      current.versions = [
        ...current.versions,
        {
          version: current.version,
          objective: current.objective,
          createdAt: now(),
          steps: structuredClone(current.steps),
        },
      ].filter((item) => item.version > 0);
      current.version = version;
      current.objective = plan.objective;
      current.steps = plan.steps.map((step) => ({ ...step, status: step.status ?? 'pending' }));
    });
  }

  async createBatch(workspaceId: ID, name = 'Lote manual') {
    await delay();
    const batch = {
      id: this.nextId('batch'), workspaceId, name, createdAt: now(), status: 'idle' as const,
      pauseRequested: false, cursor: 0, items: [],
    };
    this.update((draft) => {
      draft.batchesByWorkspace[workspaceId] = [batch, ...(draft.batchesByWorkspace[workspaceId] ?? [])];
    });
    return structuredClone(batch);
  }

  async generateQueueFromVersion(workspaceId: ID, versionId: ID) {
    await delay();
    const plan = this.snapshot.plansByWorkspace[workspaceId];
    const version = plan.versions.find((item) => String(item.version) === versionId || item.id === versionId);
    const source = version ?? { objective: plan.objective, steps: plan.steps, version: plan.version };
    const batch = {
      id: this.nextId('batch'), workspaceId,
      name: `Fila do plano v${source.version}`,
      sourceVersionId: versionId, createdAt: now(), status: 'idle' as const,
      pauseRequested: false, cursor: 0,
      items: source.steps.map((step, index) => ({
        id: this.nextId('item'), kind: 'prompt' as const, title: step.title,
        content: step.prompt || step.description, order: index, status: 'pending' as const,
      })),
    };
    this.update((draft) => {
      draft.batchesByWorkspace[workspaceId] = [batch, ...(draft.batchesByWorkspace[workspaceId] ?? [])];
    });
    return structuredClone(batch);
  }

  // Git real só existe no modo conectado; o demo mantém o diff fictício do fixture.
  private gitUnsupported(): never {
    throw new AdapterError('Git local disponível apenas no modo conectado.', 'UNSUPPORTED');
  }

  async probeRepository(_path: string): Promise<RepoProbe> { return this.gitUnsupported(); }
  async linkRepository(_projectId: ID, _path: string): Promise<GitOverview> { return this.gitUnsupported(); }
  async getGitOverview(_projectId: ID): Promise<GitOverview> { return this.gitUnsupported(); }
  async createGitWorkspace(_workspaceId: ID, _branch: string, _startRef: string): Promise<GitStatus> { return this.gitUnsupported(); }
  async openGitWorkspace(_workspaceId: ID, _input: GitOpenInput): Promise<GitStatus> { return this.gitUnsupported(); }
  async getGitStatus(_workspaceId: ID, _refresh?: boolean): Promise<GitStatus> { return this.gitUnsupported(); }
  async getGitDiff(_workspaceId: ID, _file: string, _staged: boolean, _untracked: boolean): Promise<GitDiffResult> { return this.gitUnsupported(); }
  async verifyWorkspace(_workspaceId: ID): Promise<WorkspaceVerification> { return this.gitUnsupported(); }

  // ---------------------------------------------------- motor de demonstração

  async getQueueBatch(batchId: ID): Promise<QueueBatch> {
    const workspaceId = this.getBatch(batchId).workspaceId;
    const snapshot = this.getSnapshot();
    const batch = snapshot.batchesByWorkspace[workspaceId].find((item) => item.id === batchId)!;
    return {
      id: batch.id, workspaceId, name: batch.name, status: batch.status,
      cursor: batch.cursor, pauseRequested: batch.pauseRequested, cancelRequested: false,
      blockReason: '', lastError: '', currentAttemptId: '',
      items: structuredClone(batch.items),
      attempts: structuredClone(snapshot.attemptsByWorkspace[workspaceId] ?? []).filter(
        (attempt) => attempt.batchId === batchId,
      ) as unknown as QueueBatch['attempts'],
    };
  }

  async getQueueState(workspaceId: ID): Promise<QueueState> {
    const snapshot = this.getSnapshot();
    return {
      workspaceId,
      batches: await Promise.all(
        (snapshot.batchesByWorkspace[workspaceId] ?? []).map((batch) => this.getQueueBatch(batch.id)),
      ),
      attempts: structuredClone(snapshot.attemptsByWorkspace[workspaceId] ?? []) as unknown as QueueState['attempts'],
    };
  }

  async retryAttempt(attemptId: ID, _continueSession = false): Promise<QueueBatch> {
    const snapshot = this.getSnapshot();
    const workspaceId = snapshot.activeWorkspaceId;
    const attempt = (snapshot.attemptsByWorkspace[workspaceId] ?? []).find((item) => item.id === attemptId);
    if (!attempt) throw new AdapterError('Tentativa não encontrada.', 'NOT_FOUND');
    const batch = this.getBatch(attempt.batchId);
    this.update((draft) => {
      const target = draft.batchesByWorkspace[batch.workspaceId].find((item) => item.id === batch.id)!;
      const failed = target.items.find((item) => item.id === attempt.itemId);
      if (failed) failed.status = 'pending';
      target.status = 'idle';
    });
    await this.startBatch(batch.id);
    return this.getQueueBatch(batch.id);
  }

  async getAttemptLog(attemptId: ID): Promise<LogChunk> {
    const snapshot = this.getSnapshot();
    const attempt = Object.values(snapshot.attemptsByWorkspace).flat().find((item) => item.id === attemptId);
    return {
      text: attempt ? `${attempt.output}\nResultado: ${attempt.result}` : '',
      nextOffset: 0, done: true,
    };
  }

  async getOpenCodeStatus(): Promise<OpenCodeStatus> {
    return {
      found: true, path: 'demo', source: 'demo', version: 'modo demonstração',
      capabilities: { flags: [], jsonFormat: true, session: true, model: true, agent: true, file: true },
      configured: { executable: 'demo', model: '', agent: '', timeout: '600' },
    };
  }

  async putOpenCodeConfig(_config: OpenCodeConfigInput): Promise<OpenCodeStatus['configured']> {
    return { executable: 'demo', model: '', agent: '', timeout: '600' };
  }

  async testOpenCode(): Promise<{ exitCode: number; stdout: string; stderr: string }> {
    return { exitCode: 0, stdout: 'demo: ILIMIT', stderr: '' };
  }

  // O fluxo de assistente existe somente no modo conectado.
  async getChatState(_workspaceId: ID): Promise<ChatState> { return this.gitUnsupported(); }
  async sendChatMessage(_workspaceId: ID, _conversationId: ID, _content: string): Promise<ChatState> { return this.gitUnsupported(); }
  async newChatSession(_workspaceId: ID, _conversationId: ID): Promise<ChatState> { return this.gitUnsupported(); }
  async analyzeProject(_workspaceId: ID, _objective: string): Promise<ProjectAnalysis> { return this.gitUnsupported(); }
  async generateProposal(_workspaceId: ID, _analysisId: ID, _answers: string): Promise<PlanProposal> { return this.gitUnsupported(); }
  async approveProposal(_workspaceId: ID, _proposalId: ID, _edits?: PlanInput): Promise<Plan> { return this.gitUnsupported(); }
  async createAssistantBatch(_workspaceId: ID, _versionId: ID, _force?: boolean): Promise<Batch> { return this.gitUnsupported(); }
  async buildReview(_workspaceId: ID, _batchId: ID): Promise<ReviewReport> { return this.gitUnsupported(); }
  async getReview(_workspaceId: ID): Promise<ReviewReport | null> { return this.gitUnsupported(); }

  // Entrega real (commit/push/PR) existe somente no modo conectado.
  async getDeliveryState(_workspaceId: ID): Promise<DeliveryState> { return this.gitUnsupported(); }
  async deliveryPreview(_workspaceId: ID, _selectedPaths: string[], _message: string): Promise<DeliveryPreview> { return this.gitUnsupported(); }
  async deliveryCommit(_input: {
    workspaceId: ID; previewId: ID; selectedPaths: string[]; message: string;
    batchId?: ID; attemptId?: ID;
  }): Promise<{ id: ID; hash: string; files: string[]; status: string }> { return this.gitUnsupported(); }
  async deliveryPush(_workspaceId: ID, _remote?: string, _commitId?: ID): Promise<Record<string, unknown>> { return this.gitUnsupported(); }
  async deliveryPrPreview(_workspaceId: ID, _base?: string): Promise<DeliveryPrPreview> { return this.gitUnsupported(); }
  async deliveryCreatePr(_input: DeliveryCreatePrInput): Promise<Record<string, unknown>> { return this.gitUnsupported(); }
  async deliveryRefreshPr(_workspaceId: ID): Promise<Record<string, unknown>> { return this.gitUnsupported(); }

  async getRemoteStatus(): Promise<RemoteStatus> {
    return {
      enabled: false, active: false, authenticated: false, user: '', csrf: '',
      expiresAt: '', publicOrigin: '', provider: 'local', identityHeader: '', note: '',
    };
  }
  async remoteLogin(_password: string): Promise<RemoteStatus> { return this.getRemoteStatus(); }
  async remoteLogout(): Promise<void> { /* modo demo não tem sessão */ }
  async getEvents(_workspaceId: ID, _after = 0): Promise<{
    workspaceId: ID; sequence: number; events: AppEventEnvelope[]; resync: boolean;
  }> { return this.gitUnsupported(); }
  setCsrf(_csrf: string): void { /* sem CSRF no demo */ }
  async discoveryPreview(_path: string, _github?: boolean): Promise<DiscoveryPreview> { return this.gitUnsupported(); }
  async discoveryOpen(_path: string, _choices?: Record<string, string>): Promise<DiscoveryOpenResult> { return this.gitUnsupported(); }
  async getDiscoveryPreferences(_projectId: ID): Promise<DiscoveryPreferenceRecord> { return this.gitUnsupported(); }
  async updateDiscoveryPreferences(_prefs: DiscoveryPreferenceRecord & { projectId: ID }): Promise<DiscoveryPreferenceRecord> { return this.gitUnsupported(); }
  async listWorktrees(_workspaceId: ID): Promise<{ workspaceId: ID; worktrees: DiscoveryPreview['worktrees'] }> { return this.gitUnsupported(); }

  async getHealth() {
    return { status: 'ok', version: 'demo' };
  }

  async refresh(): Promise<void> {
    // O snapshot do demo já é a fonte da verdade.
  }

  setApiStatus(status: 'unknown' | 'ok' | 'error'): void {
    if (this.snapshot.apiStatus !== status) {
      this.update((draft) => { draft.apiStatus = status; });
    }
  }
}
