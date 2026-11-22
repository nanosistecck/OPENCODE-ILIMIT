import { AdapterError, type ExtendedAdapter } from './adapter';
import { createEmptySnapshot } from './emptySnapshot';
import type {
  AppEvent,
  AppSnapshot,
  Attempt,
  Batch,
  ConnectionState,
  Conversation,
  ID,
  NewProjectInput,
  NewQueueItem,
  NewWorkspaceInput,
  PlanInput,
  Project,
  QueueItem,
  Workspace,
  WorkspaceState,
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

/**
 * Adaptador HTTP. Usa apenas caminhos relativos (/api) — o Vite faz proxy para
 * o backend local. Respostas atrasadas são descartadas por token de atualização.
 */
export class HttpAdapter implements ExtendedAdapter {
  private snapshot: AppSnapshot = createEmptySnapshot();
  private listeners = new Set<() => void>();
  private refreshToken = 0;
  private csrf = '';

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): AppSnapshot => this.snapshot;

  private patch(partial: Partial<AppSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...partial };
    for (const listener of [...this.listeners]) listener();
  }

  setApiStatus(status: 'unknown' | 'ok' | 'error'): void {
    if (this.snapshot.apiStatus !== status) this.patch({ apiStatus: status });
  }

  setCsrf(csrf: string): void {
    this.csrf = csrf;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const method = (init?.method ?? 'GET').toUpperCase();
    const write = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string> | undefined),
    };
    if (write && !headers['Idempotency-Key'] && typeof crypto !== 'undefined' && crypto.randomUUID) {
      headers['Idempotency-Key'] = crypto.randomUUID();
    }
    if (write && this.csrf) headers['X-CSRF-Token'] = this.csrf;
    let response: Response;
    try {
      response = await fetch(`/api${path}`, {
        ...init,
        credentials: 'include',
        headers,
      });
    } catch {
      this.markUnavailable();
      throw new AdapterError('API indisponível. Verifique se o backend está rodando.', 'DISCONNECTED');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => ({})) as {
        code?: string; message?: string; detail?: Record<string, unknown>;
      };
      const code = detail.code as AdapterError['code'] | undefined;
      throw new AdapterError(
        detail.message || `Erro ${response.status} na API`,
        code || (response.status === 404 ? 'NOT_FOUND' : 'VALIDATION'),
        detail.detail ?? {},
      );
    }
    this.setApiStatus('ok');
    if (this.snapshot.connection !== 'connected') this.patch({ connection: 'connected' });
    return response.json() as Promise<T>;
  }

  private markUnavailable(): void {
    this.setApiStatus('error');
    if (this.snapshot.connection !== 'error') this.patch({ connection: 'error' });
  }

  private workspaceOfBatch(batchId: ID): ID {
    for (const [workspaceId, batches] of Object.entries(this.snapshot.batchesByWorkspace)) {
      if (batches.some((batch) => batch.id === batchId)) return workspaceId;
    }
    throw new AdapterError('Lote não encontrado no espaço ativo.', 'NOT_FOUND');
  }

  // ---------------------------------------------------------------- consultas

  async getHealth(): Promise<{ status: string; version: string }> {
    try {
      const value = await this.request<{ status: string; version: string }>('/health');
      this.setApiStatus('ok');
      return value;
    } catch (error) {
      this.markUnavailable();
      throw error;
    }
  }

  async refresh(): Promise<void> {
    const token = ++this.refreshToken;
    try {
      const projects = await this.request<Project[]>('/projects');
      // Um projeto aberto por descoberta pode não ser o primeiro da lista: carregar
      // os espaços de todos os projetos preserva o espaço ativo entre atualizações.
      const grouped = await Promise.all(
        projects.map((project) => this.request<Workspace[]>(`/projects/${project.id}/workspaces`)),
      );
      const workspaces = grouped.flat();
      if (token !== this.refreshToken) return;

      const activeWorkspaceId = workspaces.some((item) => item.id === this.snapshot.activeWorkspaceId)
        ? this.snapshot.activeWorkspaceId
        : (workspaces[0]?.id ?? '');
      this.patch({ projects, workspaces, activeWorkspaceId });

      if (!activeWorkspaceId) {
        this.patch({
          conversationsByWorkspace: {}, plansByWorkspace: {}, batchesByWorkspace: {},
          attemptsByWorkspace: {}, gitByWorkspace: {},
        });
        return;
      }

      const [state, batches, attempts] = await Promise.all([
        this.request<WorkspaceState>(`/workspaces/${activeWorkspaceId}/state`),
        this.request<Batch[]>(`/workspaces/${activeWorkspaceId}/batches`),
        this.request<Attempt[]>(`/workspaces/${activeWorkspaceId}/attempts`),
      ]);
      if (token !== this.refreshToken) return;

      this.patch({
        conversationsByWorkspace: {
          ...this.snapshot.conversationsByWorkspace,
          [activeWorkspaceId]: state.conversation,
        },
        plansByWorkspace: state.plan
          ? { ...this.snapshot.plansByWorkspace, [activeWorkspaceId]: state.plan }
          : this.snapshot.plansByWorkspace,
        gitByWorkspace: { ...this.snapshot.gitByWorkspace, [activeWorkspaceId]: state.git },
        batchesByWorkspace: { ...this.snapshot.batchesByWorkspace, [activeWorkspaceId]: batches },
        attemptsByWorkspace: { ...this.snapshot.attemptsByWorkspace, [activeWorkspaceId]: attempts },
        connection: 'connected',
      });
    } catch (error) {
      if (token === this.refreshToken) this.markUnavailable();
      throw error;
    }
  }

  async setActiveWorkspace(workspaceId: ID): Promise<void> {
    const token = ++this.refreshToken;
    this.patch({ activeWorkspaceId: workspaceId });
    try {
      const [state, batches, attempts] = await Promise.all([
        this.request<WorkspaceState>(`/workspaces/${workspaceId}/state`),
        this.request<Batch[]>(`/workspaces/${workspaceId}/batches`),
        this.request<Attempt[]>(`/workspaces/${workspaceId}/attempts`),
      ]);
      // Troca rápida: uma resposta da branch anterior é descartada.
      if (token !== this.refreshToken) return;
      this.patch({
        conversationsByWorkspace: {
          ...this.snapshot.conversationsByWorkspace,
          [workspaceId]: state.conversation,
        },
        plansByWorkspace: state.plan
          ? { ...this.snapshot.plansByWorkspace, [workspaceId]: state.plan }
          : this.snapshot.plansByWorkspace,
        gitByWorkspace: { ...this.snapshot.gitByWorkspace, [workspaceId]: state.git },
        batchesByWorkspace: { ...this.snapshot.batchesByWorkspace, [workspaceId]: batches },
        attemptsByWorkspace: { ...this.snapshot.attemptsByWorkspace, [workspaceId]: attempts },
      });
    } catch (error) {
      if (token === this.refreshToken) this.markUnavailable();
      throw error;
    }
  }

  async listProjects(): Promise<Project[]> {
    return this.request<Project[]>('/projects');
  }

  async listWorkspaces(projectId: ID): Promise<Workspace[]> {
    return this.request<Workspace[]>(`/projects/${projectId}/workspaces`);
  }

  async getWorkspaceState(workspaceId: ID): Promise<WorkspaceState> {
    return this.request<WorkspaceState>(`/workspaces/${workspaceId}/state`);
  }

  async listBatches(workspaceId: ID): Promise<Batch[]> {
    return this.request<Batch[]>(`/workspaces/${workspaceId}/batches`);
  }

  async listAttempts(workspaceId: ID): Promise<Attempt[]> {
    return this.request<Attempt[]>(`/workspaces/${workspaceId}/attempts`);
  }

  async listEvents(): Promise<AppEvent[]> {
    return []; // Eventos persistidos entram com o motor de fila.
  }

  // ------------------------------------------------------------------ chat

  async createConversation(workspaceId: ID): Promise<Conversation> {
    const conversation = await this.request<Conversation>(`/workspaces/${workspaceId}/conversations`, {
      method: 'POST',
    });
    await this.refresh();
    return conversation;
  }

  async sendMessage(workspaceId: ID, conversationId: ID, content: string): Promise<void> {
    await this.request(
      `/workspaces/${workspaceId}/messages?conversationId=${encodeURIComponent(conversationId)}`,
      { method: 'POST', body: JSON.stringify({ content }) },
    );
    await this.refresh();
  }

  // ------------------------------------------------------------------ plano

  async savePlan(workspaceId: ID, plan: PlanInput): Promise<void> {
    await this.request(`/plans/${workspaceId}`, { method: 'PUT', body: JSON.stringify(plan) });
    await this.refresh();
  }

  async reviewPlan(workspaceId: ID): Promise<void> {
    await this.request(`/workspaces/${workspaceId}/plan/review`, { method: 'POST' });
    await this.refresh();
  }

  async generateQueue(workspaceId: ID): Promise<Batch> {
    return this.generateQueueFromVersion(workspaceId, '');
  }

  async generateQueueFromVersion(workspaceId: ID, versionId: ID): Promise<Batch> {
    const query = versionId ? `?versionId=${encodeURIComponent(versionId)}` : '';
    const batch = await this.request<Batch>(`/workspaces/${workspaceId}/queue${query}`, { method: 'POST' });
    await this.refresh();
    return batch;
  }

  // ------------------------------------------------------------------- fila

  async createBatch(workspaceId: ID, name = 'Lote manual'): Promise<Batch> {
    const batch = await this.request<Batch>(`/batches?workspaceId=${encodeURIComponent(workspaceId)}`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
    await this.refresh();
    return batch;
  }

  async addQueueItems(batchId: ID, items: NewQueueItem[]): Promise<void> {
    const workspaceId = this.workspaceOfBatch(batchId);
    await this.request(`/batches/${batchId}/items?workspaceId=${encodeURIComponent(workspaceId)}`, {
      method: 'POST', body: JSON.stringify(items),
    });
    await this.refresh();
  }

  async updateQueueItem(batchId: ID, itemId: ID, patch: Partial<Pick<QueueItem, 'title' | 'content'>>): Promise<void> {
    const workspaceId = this.workspaceOfBatch(batchId);
    await this.request(
      `/batches/${batchId}/items/${itemId}?workspaceId=${encodeURIComponent(workspaceId)}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
    await this.refresh();
  }

  async removeQueueItem(batchId: ID, itemId: ID): Promise<void> {
    const workspaceId = this.workspaceOfBatch(batchId);
    await this.request(
      `/batches/${batchId}/items/${itemId}?workspaceId=${encodeURIComponent(workspaceId)}`,
      { method: 'DELETE' },
    );
    await this.refresh();
  }

  async moveQueueItem(batchId: ID, itemId: ID, direction: -1 | 1): Promise<void> {
    const batch = Object.values(this.snapshot.batchesByWorkspace)
      .flat()
      .find((item) => item.id === batchId);
    if (!batch) throw new AdapterError('Lote não encontrado.', 'NOT_FOUND');
    const index = batch.items.findIndex((item) => item.id === itemId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= batch.items.length) return;
    const orderedIds = batch.items.map((item) => item.id);
    [orderedIds[index], orderedIds[target]] = [orderedIds[target], orderedIds[index]];
    const workspaceId = this.workspaceOfBatch(batchId);
    await this.request(`/batches/${batchId}/items/reorder?workspaceId=${encodeURIComponent(workspaceId)}`, {
      method: 'POST', body: JSON.stringify({ orderedIds }),
    });
    await this.refresh();
  }

  // --------------------------------------------------------- cadastro geral

  async createProject(input: NewProjectInput): Promise<Project> {
    const project = await this.request<Project>('/projects', {
      method: 'POST', body: JSON.stringify(input),
    });
    await this.refresh();
    return project;
  }

  async createWorkspace(projectId: ID, input: NewWorkspaceInput): Promise<Workspace> {
    const workspace = await this.request<Workspace>(`/projects/${projectId}/workspaces`, {
      method: 'POST', body: JSON.stringify(input),
    });
    await this.refresh();
    return workspace;
  }

  // ------------------------------------------------------------------- Git

  async probeRepository(path: string): Promise<RepoProbe> {
    return this.request<RepoProbe>('/git/probe', {
      method: 'POST', body: JSON.stringify({ path }),
    });
  }

  async linkRepository(projectId: ID, path: string): Promise<GitOverview> {
    const result = await this.request<GitOverview>(`/git/projects/${projectId}/repository`, {
      method: 'POST', body: JSON.stringify({ path }),
    });
    await this.refresh();
    return result;
  }

  async getGitOverview(projectId: ID): Promise<GitOverview> {
    return this.request<GitOverview>(`/git/projects/${projectId}/overview`);
  }

  async createGitWorkspace(workspaceId: ID, branch: string, startRef: string): Promise<GitStatus> {
    const result = await this.request<GitStatus>(`/git/workspaces/${workspaceId}/branches`, {
      method: 'POST', body: JSON.stringify({ branch, startRef }),
    });
    await this.refresh();
    return result;
  }

  async openGitWorkspace(workspaceId: ID, input: GitOpenInput): Promise<GitStatus> {
    const result = await this.request<GitStatus>(`/git/workspaces/${workspaceId}/open`, {
      method: 'POST', body: JSON.stringify(input),
    });
    await this.refresh();
    return result;
  }

  async getGitStatus(workspaceId: ID, refresh = false): Promise<GitStatus> {
    if (refresh) {
      return this.request<GitStatus>(`/git/workspaces/${workspaceId}/refresh`, { method: 'POST' });
    }
    return this.request<GitStatus>(`/git/workspaces/${workspaceId}/status`);
  }

  async getGitDiff(
    workspaceId: ID, file: string, staged: boolean, untracked: boolean,
  ): Promise<GitDiffResult> {
    const query = new URLSearchParams({ file, staged: String(staged), untracked: String(untracked) });
    return this.request<GitDiffResult>(`/git/workspaces/${workspaceId}/diff?${query.toString()}`);
  }

  async verifyWorkspace(workspaceId: ID): Promise<WorkspaceVerification> {
    return this.request<WorkspaceVerification>(`/git/workspaces/${workspaceId}/verify`, {
      method: 'POST',
    });
  }

  // ------------------------------------------------------- motor da fila

  async startBatch(batchId: ID): Promise<void> {
    await this.request(`/queue/batches/${batchId}/start`, { method: 'POST' });
    await this.refresh();
  }

  async requestPause(batchId: ID): Promise<void> {
    await this.request(`/queue/batches/${batchId}/pause`, { method: 'POST' });
    await this.refresh();
  }

  async resumeBatch(batchId: ID): Promise<void> {
    await this.request(`/queue/batches/${batchId}/resume`, { method: 'POST' });
    await this.refresh();
  }

  async cancelBatch(batchId: ID): Promise<void> {
    await this.request(`/queue/batches/${batchId}/cancel`, { method: 'POST' });
    await this.refresh();
  }

  async getQueueBatch(batchId: ID): Promise<QueueBatch> {
    return this.request<QueueBatch>(`/queue/batches/${batchId}`);
  }

  async getQueueState(workspaceId: ID): Promise<QueueState> {
    return this.request<QueueState>(`/queue/state?workspaceId=${encodeURIComponent(workspaceId)}`);
  }

  async retryAttempt(attemptId: ID, continueSession = false): Promise<QueueBatch> {
    const result = await this.request<QueueBatch>(`/queue/attempts/${attemptId}/retry`, {
      method: 'POST', body: JSON.stringify({ continueSession }),
    });
    await this.refresh();
    return result;
  }

  async getAttemptLog(attemptId: ID, offset = 0, limit = 16000): Promise<LogChunk> {
    return this.request<LogChunk>(
      `/queue/attempts/${attemptId}/log?offset=${offset}&limit=${limit}`,
    );
  }

  async getOpenCodeStatus(): Promise<OpenCodeStatus> {
    return this.request<OpenCodeStatus>('/queue/opencode/status');
  }

  async putOpenCodeConfig(config: OpenCodeConfigInput): Promise<OpenCodeStatus['configured']> {
    return this.request<OpenCodeStatus['configured']>('/queue/opencode/config', {
      method: 'PUT', body: JSON.stringify(config),
    });
  }

  async testOpenCode(): Promise<{ exitCode: number; stdout: string; stderr: string }> {
    return this.request('/queue/opencode/test', { method: 'POST' });
  }

  // ------------------------------------------------------- chat e planejamento

  async getChatState(workspaceId: ID): Promise<ChatState> {
    return this.request<ChatState>(`/assistant/chat/${workspaceId}/state`);
  }

  async sendChatMessage(workspaceId: ID, conversationId: ID, content: string): Promise<ChatState> {
    const result = await this.request<ChatState>(
      `/assistant/chat/${workspaceId}/messages?conversationId=${encodeURIComponent(conversationId)}`,
      { method: 'POST', body: JSON.stringify({ content }) },
    );
    await this.refresh();
    return result;
  }

  async newChatSession(workspaceId: ID, conversationId: ID): Promise<ChatState> {
    return this.request<ChatState>(
      `/assistant/chat/${workspaceId}/new-session?conversationId=${encodeURIComponent(conversationId)}`,
      { method: 'POST' },
    );
  }

  async analyzeProject(workspaceId: ID, objective: string): Promise<ProjectAnalysis> {
    const result = await this.request<ProjectAnalysis>(`/assistant/analyze/${workspaceId}`, {
      method: 'POST', body: JSON.stringify({ objective }),
    });
    await this.refresh();
    return result;
  }

  async generateProposal(workspaceId: ID, analysisId: ID, answers: string): Promise<PlanProposal> {
    return this.request<PlanProposal>(`/assistant/plan/${workspaceId}/proposal`, {
      method: 'POST', body: JSON.stringify({ analysisId, answers }),
    });
  }

  async approveProposal(workspaceId: ID, proposalId: ID, edits?: PlanInput): Promise<Plan> {
    const result = await this.request<Plan>(`/assistant/plan/${workspaceId}/approve`, {
      method: 'POST', body: JSON.stringify({ proposalId, ...(edits ?? {}) }),
    });
    await this.refresh();
    return result;
  }

  async createAssistantBatch(workspaceId: ID, versionId: ID, force = false): Promise<Batch> {
    const result = await this.request<Batch>(`/assistant/plan/${workspaceId}/batch`, {
      method: 'POST', body: JSON.stringify({ versionId, force }),
    });
    await this.refresh();
    return result;
  }

  async buildReview(workspaceId: ID, batchId: ID): Promise<ReviewReport> {
    return this.request<ReviewReport>(
      `/assistant/review/${workspaceId}?batchId=${encodeURIComponent(batchId)}`,
      { method: 'POST' },
    );
  }

  async getReview(workspaceId: ID): Promise<ReviewReport | null> {
    return this.request<ReviewReport | null>(`/assistant/review/${workspaceId}`);
  }

  // ------------------------------------------------------------- entrega

  async getDeliveryState(workspaceId: ID): Promise<DeliveryState> {
    return this.request<DeliveryState>(
      `/delivery/state?workspaceId=${encodeURIComponent(workspaceId)}`,
    );
  }

  async deliveryPreview(workspaceId: ID, selectedPaths: string[], message: string): Promise<DeliveryPreview> {
    return this.request<DeliveryPreview>('/delivery/preview', {
      method: 'POST', body: JSON.stringify({ workspaceId, selectedPaths, message }),
    });
  }

  async deliveryCommit(input: {
    workspaceId: ID; previewId: ID; selectedPaths: string[]; message: string;
    batchId?: ID; attemptId?: ID;
  }): Promise<{ id: ID; hash: string; files: string[]; status: string }> {
    const result = await this.request<{ id: ID; hash: string; files: string[]; status: string }>(
      '/delivery/commit', { method: 'POST', body: JSON.stringify(input) },
    );
    await this.refresh();
    return result;
  }

  async deliveryPush(workspaceId: ID, remote = '', commitId = ''): Promise<Record<string, unknown>> {
    const result = await this.request<Record<string, unknown>>('/delivery/push', {
      method: 'POST', body: JSON.stringify({ workspaceId, remote, commitId }),
    });
    await this.refresh();
    return result;
  }

  async deliveryPrPreview(workspaceId: ID, base = ''): Promise<DeliveryPrPreview> {
    return this.request<DeliveryPrPreview>('/delivery/pr/preview', {
      method: 'POST', body: JSON.stringify({ workspaceId, base }),
    });
  }

  async deliveryCreatePr(input: DeliveryCreatePrInput): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/delivery/pr', {
      method: 'POST', body: JSON.stringify(input),
    });
  }

  async deliveryRefreshPr(workspaceId: ID): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/delivery/pr/refresh', {
      method: 'POST', body: JSON.stringify({ workspaceId }),
    });
  }

  // ------------------------------------------------------------- remoto

  async getRemoteStatus(): Promise<RemoteStatus> {
    const result = await this.request<RemoteStatus>('/remote/status');
    if (result.csrf) this.setCsrf(result.csrf);
    return result;
  }

  async remoteLogin(password: string): Promise<RemoteStatus> {
    const result = await this.request<RemoteStatus>('/remote/login', {
      method: 'POST', body: JSON.stringify({ password }),
    });
    if (result.csrf) this.setCsrf(result.csrf);
    return result;
  }

  async remoteLogout(): Promise<void> {
    await this.request('/remote/logout', { method: 'POST' });
    this.setCsrf('');
  }

  async getEvents(workspaceId: ID, after = 0): Promise<{
    workspaceId: ID; sequence: number; events: AppEventEnvelope[]; resync: boolean;
  }> {
    return this.request(
      `/events?workspaceId=${encodeURIComponent(workspaceId)}&after=${after}`,
    );
  }

  // --------------------------------------------------------- descoberta

  async discoveryPreview(path: string, github = true): Promise<DiscoveryPreview> {
    return this.request<DiscoveryPreview>('/discovery/preview', {
      method: 'POST', body: JSON.stringify({ path, github }),
    });
  }

  async discoveryOpen(path: string, choices: Record<string, string> = {}): Promise<DiscoveryOpenResult> {
    const result = await this.request<DiscoveryOpenResult>('/discovery/open', {
      method: 'POST', body: JSON.stringify({ path, choices }),
    });
    await this.refresh();
    return result;
  }

  async getDiscoveryPreferences(projectId: ID): Promise<DiscoveryPreferenceRecord> {
    return this.request<DiscoveryPreferenceRecord>(
      `/discovery/preferences?projectId=${encodeURIComponent(projectId)}`,
    );
  }

  async updateDiscoveryPreferences(
    prefs: DiscoveryPreferenceRecord & { projectId: ID },
  ): Promise<DiscoveryPreferenceRecord> {
    return this.request<DiscoveryPreferenceRecord>('/discovery/preferences', {
      method: 'PUT', body: JSON.stringify(prefs),
    });
  }

  async listWorktrees(workspaceId: ID): Promise<{ workspaceId: ID; worktrees: DiscoveryPreview['worktrees'] }> {
    return this.request(
      `/discovery/worktrees?workspaceId=${encodeURIComponent(workspaceId)}`,
    );
  }

  async setConnection(state: ConnectionState): Promise<void> {
    if (state === 'connected') {
      await this.getHealth();
    } else {
      this.patch({ connection: state });
    }
  }
}
