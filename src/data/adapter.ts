import type {
  AppEvent,
  AppSnapshot,
  Batch,
  ConnectionState,
  ID,
  NewQueueItem,
  Project,
  Plan,
  QueueItem,
  Workspace,
  WorkspaceState,
  Attempt,
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
  OpenCodeStatus,
  OpenCodeConfigInput,
  LogChunk,
  RemoteStatus,
  AppEventEnvelope,
  DiscoveryPreview,
  DiscoveryOpenResult,
  DiscoveryPreferenceRecord,
  ChatState,
  ProjectAnalysis,
  PlanProposal,
  ReviewReport,
  DeliveryState,
  DeliveryPreview,
  DeliveryPrPreview,
  DeliveryCreatePrInput,
} from '../domain/types';

/**
 * Contrato usado por TODAS as telas. Hoje implementado por MockAdapter;
 * no Prompt 02, a implementação HTTP/WebSocket deve honrar os mesmos métodos.
 *
 * Convenção: todo método assíncrono pode rejeitar com `AdapterError`.
 * Uma ação "solicitada" (ex.: requestPause) NÃO é a confirmação do resultado:
 * o estado confirmado chega via snapshot/evento.
 */
export interface Adapter {
  /** Compatível com useSyncExternalStore: notifica após cada mutação. */
  subscribe(listener: () => void): () => void;
  /** Deve devolver sempre a MESMA referência até que ocorra uma mutação. */
  getSnapshot(): AppSnapshot;

  listProjects(): Promise<Project[]>;
  listWorkspaces(projectId: ID): Promise<Workspace[]>;
  getWorkspaceState(workspaceId: ID): Promise<WorkspaceState>;
  setActiveWorkspace(workspaceId: ID): Promise<void>;

  sendMessage(workspaceId: ID, conversationId: ID, content: string): Promise<void>;

  reviewPlan(workspaceId: ID): Promise<void>;
  generateQueue(workspaceId: ID): Promise<Batch>;

  addQueueItems(batchId: ID, items: NewQueueItem[]): Promise<void>;
  updateQueueItem(batchId: ID, itemId: ID, patch: Partial<Pick<QueueItem, 'title' | 'content'>>): Promise<void>;
  removeQueueItem(batchId: ID, itemId: ID): Promise<void>;
  moveQueueItem(batchId: ID, itemId: ID, direction: -1 | 1): Promise<void>;

  startBatch(batchId: ID): Promise<void>;
  requestPause(batchId: ID): Promise<void>;
  resumeBatch(batchId: ID): Promise<void>;
  cancelBatch(batchId: ID): Promise<void>;

  listBatches(workspaceId: ID): Promise<Batch[]>;
  listAttempts(workspaceId: ID): Promise<Attempt[]>;
  listEvents(): Promise<AppEvent[]>;

  /** Simula saída/entrada do PC. O último estado recebido é preservado. */
  setConnection(state: ConnectionState): Promise<void>;
}

/**
 * Operações de cadastro/edição usadas no modo conectado. O MockAdapter também
 * as implementa para manter as telas independentes da origem dos dados.
 */
export interface ExtendedAdapter extends Adapter {
  createProject(input: NewProjectInput): Promise<Project>;
  createWorkspace(projectId: ID, input: NewWorkspaceInput): Promise<Workspace>;
  createConversation(workspaceId: ID): Promise<Conversation>;
  savePlan(workspaceId: ID, plan: PlanInput): Promise<void>;
  createBatch(workspaceId: ID, name?: string): Promise<Batch>;
  generateQueueFromVersion(workspaceId: ID, versionId: ID): Promise<Batch>;

  probeRepository(path: string): Promise<RepoProbe>;
  linkRepository(projectId: ID, path: string): Promise<GitOverview>;
  getGitOverview(projectId: ID): Promise<GitOverview>;
  createGitWorkspace(workspaceId: ID, branch: string, startRef: string): Promise<GitStatus>;
  openGitWorkspace(workspaceId: ID, input: GitOpenInput): Promise<GitStatus>;
  getGitStatus(workspaceId: ID, refresh?: boolean): Promise<GitStatus>;
  getGitDiff(workspaceId: ID, file: string, staged: boolean, untracked: boolean): Promise<GitDiffResult>;
  verifyWorkspace(workspaceId: ID): Promise<WorkspaceVerification>;

  getQueueBatch(batchId: ID): Promise<QueueBatch>;
  getQueueState(workspaceId: ID): Promise<QueueState>;
  retryAttempt(attemptId: ID, continueSession?: boolean): Promise<QueueBatch>;
  getAttemptLog(attemptId: ID, offset?: number, limit?: number): Promise<LogChunk>;
  getOpenCodeStatus(): Promise<OpenCodeStatus>;
  putOpenCodeConfig(config: OpenCodeConfigInput): Promise<OpenCodeStatus['configured']>;
  testOpenCode(): Promise<{ exitCode: number; stdout: string; stderr: string }>;

  getChatState(workspaceId: ID): Promise<ChatState>;
  sendChatMessage(workspaceId: ID, conversationId: ID, content: string): Promise<ChatState>;
  newChatSession(workspaceId: ID, conversationId: ID): Promise<ChatState>;
  analyzeProject(workspaceId: ID, objective: string): Promise<ProjectAnalysis>;
  generateProposal(workspaceId: ID, analysisId: ID, answers: string): Promise<PlanProposal>;
  approveProposal(workspaceId: ID, proposalId: ID, edits?: PlanInput): Promise<Plan>;
  createAssistantBatch(workspaceId: ID, versionId: ID, force?: boolean): Promise<Batch>;
  buildReview(workspaceId: ID, batchId: ID): Promise<ReviewReport>;
  getReview(workspaceId: ID): Promise<ReviewReport | null>;

  getDeliveryState(workspaceId: ID): Promise<DeliveryState>;
  deliveryPreview(workspaceId: ID, selectedPaths: string[], message: string): Promise<DeliveryPreview>;
  deliveryCommit(input: {
    workspaceId: ID; previewId: ID; selectedPaths: string[]; message: string;
    batchId?: ID; attemptId?: ID;
  }): Promise<{ id: ID; hash: string; files: string[]; status: string }>;
  deliveryPush(workspaceId: ID, remote?: string, commitId?: ID): Promise<Record<string, unknown>>;
  deliveryPrPreview(workspaceId: ID, base?: string): Promise<DeliveryPrPreview>;
  deliveryCreatePr(input: DeliveryCreatePrInput): Promise<Record<string, unknown>>;
  deliveryRefreshPr(workspaceId: ID): Promise<Record<string, unknown>>;

  getRemoteStatus(): Promise<RemoteStatus>;
  remoteLogin(password: string): Promise<RemoteStatus>;
  remoteLogout(): Promise<void>;
  getEvents(workspaceId: ID, after?: number): Promise<{
    workspaceId: ID; sequence: number; events: AppEventEnvelope[]; resync: boolean;
  }>;
  setCsrf(csrf: string): void;

  discoveryPreview(path: string, github?: boolean): Promise<DiscoveryPreview>;
  discoveryOpen(path: string, choices?: Record<string, string>): Promise<DiscoveryOpenResult>;
  getDiscoveryPreferences(projectId: ID): Promise<DiscoveryPreferenceRecord>;
  updateDiscoveryPreferences(prefs: DiscoveryPreferenceRecord & { projectId: ID }): Promise<DiscoveryPreferenceRecord>;
  listWorktrees(workspaceId: ID): Promise<{ workspaceId: ID; worktrees: DiscoveryPreview['worktrees'] }>;

  getHealth(): Promise<{ status: string; version: string }>;
  /** Recarrega o snapshot da origem de dados atual. */
  refresh(): Promise<void>;
  setApiStatus(status: 'unknown' | 'ok' | 'error'): void;
}

export class AdapterError extends Error {
  constructor(
    message: string,
    readonly code: 'DISCONNECTED' | 'NOT_FOUND' | 'INVALID_STATE' | 'UNSUPPORTED' | 'VALIDATION' | 'UNKNOWN' = 'UNKNOWN',
    readonly detail: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'AdapterError';
  }
}
