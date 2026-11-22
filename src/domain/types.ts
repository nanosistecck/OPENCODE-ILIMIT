/**
 * Contrato de domínio do OPENCODE ILIMIT.
 *
 * Regras de vínculo (mantidas no Prompt 02):
 * - Projeto, espaço, lote e tentativa têm IDs estáveis.
 * - `workspaceId` vincula conversa, plano, fila e histórico.
 * - `branch` é informação de exibição; o vínculo entre entidades é sempre o ID.
 */

export type ID = string;

export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'error';
export type Theme = 'light' | 'dark';
export type AppMode = 'demo' | 'connected';
export type ApiStatus = 'unknown' | 'ok' | 'error';

export type WorkspaceKind = 'base' | 'worktree';

export interface Project {
  id: ID;
  name: string;
  description: string;
  baseBranch: string;
  workspaceIds: ID[];
  objective?: string;
  rules?: string;
  repoPath?: string | null;
}

export interface Workspace {
  id: ID;
  projectId: ID;
  name: string;
  /** Apenas exibição. Nunca use como chave de vínculo. */
  branch: string;
  base: string;
  kind: WorkspaceKind;
  createdAt: string;
  workDir?: string;
  baseBranch?: string;
}

export type MessageRole = 'user' | 'assistant';
export type MessageStatus = 'sending' | 'sent' | 'failed';

export interface Message {
  id: ID;
  conversationId: ID;
  role: MessageRole;
  content: string;
  createdAt: string;
  status: MessageStatus;
}

export interface AgentActivity {
  id: ID;
  label: string;
  detail: string;
  status: 'running' | 'done' | 'error';
  createdAt: string;
}

export interface Conversation {
  id: ID;
  workspaceId: ID;
  title: string;
  messages: Message[];
  activity: AgentActivity[];
}

export type PlanStepStatus = 'pending' | 'in_progress' | 'done' | 'blocked';

export interface PlanStep {
  id: ID;
  order: number;
  title: string;
  description: string;
  /** IDs de outras etapas das quais esta depende. */
  dependencies: ID[];
  acceptanceCriteria: string;
  status: PlanStepStatus;
  prompt?: string;
}

export interface PlanVersion {
  id?: ID;
  version: number;
  objective: string;
  createdAt: string;
  steps: PlanStep[];
}

export interface Plan {
  id: ID;
  workspaceId: ID;
  objective: string;
  version: number;
  status: 'draft' | 'in_review' | 'approved' | 'superseded';
  versions: PlanVersion[];
  steps: PlanStep[];
}

export type QueueItemKind = 'prompt' | 'file';
export type QueueItemStatus = 'pending' | 'running' | 'done' | 'failed' | 'cancelled';

export interface QueueItem {
  id: ID;
  kind: QueueItemKind;
  title: string;
  content: string;
  fileName?: string;
  order: number;
  status: QueueItemStatus;
}

/**
 * `pausing` = pausa SOLICITADA (aguardando o fim da etapa atual).
 * `paused`  = pausa CONFIRMADA (etapa atual já encerrada).
 */
export type BatchStatus =
  | 'idle'
  | 'running'
  | 'pausing'
  | 'paused'
  | 'failed'
  | 'cancelled'
  | 'completed'
  | 'interrupted';

export interface Batch {
  id: ID;
  workspaceId: ID;
  name: string;
  createdAt: string;
  status: BatchStatus;
  pauseRequested: boolean;
  /** Índice do próximo item a executar. */
  cursor: number;
  items: QueueItem[];
  sourceVersionId?: ID | null;
}

export type AttemptStatus =
  | 'running' | 'success' | 'failure' | 'cancelled' | 'interrupted' | 'inconclusive';

export interface Attempt {
  id: ID;
  batchId: ID;
  workspaceId: ID;
  itemId: ID;
  itemTitle: string;
  stepIndex: number;
  prompt: string;
  output: string;
  result: string;
  status: AttemptStatus;
  /** Branch exibida no histórico. */
  branch: string;
  /** Vínculo real com o espaço. */
  workspaceRef: ID;
  startedAt: string;
  finishedAt?: string;
}

export type VerificationStatus = 'success' | 'failure' | 'pending' | 'skipped';

export interface Verification {
  id: ID;
  name: string;
  status: VerificationStatus;
  conclusion: string;
}

export interface PullRequest {
  id: ID;
  title: string;
  source: string;
  target: string;
  status: 'open' | 'merged' | 'draft';
  verifications: Verification[];
}

export interface Commit {
  id: ID;
  hash: string;
  message: string;
  author: string;
  createdAt: string;
}

export interface GitDiffLine {
  kind: 'meta' | 'context' | 'add' | 'remove';
  content: string;
}

export interface GitInfo {
  workspaceId: ID;
  branch: string;
  base: string;
  workDir?: string;
  head?: string;
  repoRoot?: string;
  gitStatus?: 'pending' | 'ready' | 'error';
  linked?: boolean;
  summary?: GitStatusSummary;
  files?: GitFileChange[];
  operations?: string[];
  verification?: WorkspaceVerification;
  registeredOnly?: boolean;
  diff: GitDiffLine[];
  commits: Commit[];
  pullRequest: PullRequest;
  /** No modo demo, o conteúdo é explicitamente fictício. */
  simulated: true;
}

export interface GitFileChange {
  path: string;
  oldPath: string;
  indexStatus: string;
  worktreeStatus: string;
  staged: boolean;
  unstaged: boolean;
  untracked: boolean;
  conflict: boolean;
  binary: boolean;
}

export interface GitStatusSummary {
  total: number;
  staged: number;
  unstaged: number;
  untracked: number;
  conflicts: number;
}

export interface GitStatus {
  workspaceId: ID;
  available: boolean;
  reason?: string;
  path: string;
  branch: string;
  head: string;
  files: GitFileChange[];
  summary: GitStatusSummary;
  operations: string[];
}

export interface GitDiffResult {
  workspaceId: ID;
  file: string;
  staged: boolean;
  available: boolean;
  text?: string;
  binary?: boolean;
  truncated?: boolean;
  reason?: string;
}

export interface GitRef {
  ref: string;
  name: string;
  commit: string;
  subject: string;
  kind: 'local' | 'remote';
  label?: string;
}

export interface GitOverview {
  projectId: ID;
  root: string;
  commonDir: string;
  state: { branch: string; head: string; detached: boolean; hasCommits: boolean };
  refs: {
    local: GitRef[];
    remote: GitRef[];
    suggestions: Array<{ name: string; options: GitRef[] }>;
  };
  worktrees: Array<{ path: string; head: string; branch: string; detached: boolean; locked: boolean }>;
}

export interface RepoProbe {
  ok: boolean;
  root: string;
  commonDir: string;
  isWorktree: boolean;
  error: string;
  state?: GitOverview['state'];
  refs?: GitOverview['refs'];
}

export interface WorkspaceVerification {
  workspaceId: ID;
  path: string;
  branch: string;
  observedBranch: string;
  head: string;
  boundHead: string;
  originCommit: string;
  ready: boolean;
  reasons: string[];
  localChanges: GitStatusSummary;
  operations: string[];
}

export interface GitOpenInput {
  action: 'link' | 'attach' | 'remote';
  path?: string;
  sourceRef?: string;
  branch?: string;
}

export interface QueueAttempt {
  id: ID;
  batchId: ID;
  itemId: ID;
  workspaceId: ID;
  sessionId?: ID | null;
  promptSnapshot: string;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  status: AttemptStatus;
  result: string;
  error: string;
  logPath: string;
  headBefore?: string;
  headAfter?: string;
  statusBefore?: GitStatusSummary;
  statusAfter?: GitStatusSummary;
  requestedModel?: string | null;
  observedModel?: string | null;
  requestedAgent?: string | null;
  exitCode?: number | null;
  events: Array<Record<string, unknown>>;
  cancelRequested: boolean;
  resumeOf?: ID | null;
  acceptanceCriteria?: string;
  branch?: string;
  workDir?: string;
}

export interface QueueItemFull extends QueueItem {
  dependsOn?: ID[];
  acceptanceCriteria?: string;
}

export interface QueueBatch {
  id: ID;
  workspaceId: ID;
  name: string;
  status: BatchStatus;
  cursor: number;
  pauseRequested: boolean;
  cancelRequested: boolean;
  blockReason: string;
  lastError: string;
  currentAttemptId: ID;
  items: QueueItemFull[];
  attempts: QueueAttempt[];
}

export interface QueueState {
  workspaceId: ID;
  batches: QueueBatch[];
  attempts: QueueAttempt[];
}

export interface OpenCodeStatus {
  found: boolean;
  path: string;
  source: string;
  version: string;
  capabilities: {
    flags: string[];
    jsonFormat: boolean;
    session: boolean;
    model: boolean;
    agent: boolean;
    file: boolean;
  };
  configured: { executable: string; model: string; agent: string; timeout: string };
}

export interface OpenCodeConfigInput {
  executable?: string;
  model?: string;
  agent?: string;
  timeout?: string;
}

export interface LogChunk {
  text: string;
  nextOffset: number;
  done: boolean;
}

export interface ChatMessageFull extends Message {
  error: string;
  partial: string;
  chatAttemptId: string;
  sessionId: string;
  kind: string;
}

export interface ConversationFull extends Conversation {
  sessionId: string;
  sessionKind: string;
  sessionStatus: string;
  summary: string;
  updatedAt: string;
  messages: ChatMessageFull[];
}

export interface ChatState {
  workspaceId: ID;
  conversations: ConversationFull[];
  queueRunning: boolean;
}

export interface ProjectAnalysis {
  id: ID;
  workspaceId: ID;
  content: string;
  evidence: string[];
  assumptions: string[];
  questions: string[];
  gitState: WorkspaceVerification;
  valid: boolean;
  error: string;
}

export interface ProposalStep {
  id: ID;
  order: number;
  title: string;
  objective?: string;
  description?: string;
  dependencies: ID[];
  prompt: string;
  acceptanceCriteria: string;
  reason?: string;
}

export interface PlanProposal {
  id: ID;
  workspaceId: ID;
  analysisId: ID;
  status: 'draft' | 'invalid' | 'approved' | 'superseded';
  objective: string;
  scope: string;
  decisions: Array<{ text: string; needsAnswer: boolean }>;
  questions: string[];
  steps: ProposalStep[];
  validationError: string;
  createdAt: string;
}

export interface DiscoveryPreferenceRecord {
  baseBranch: string;
  publishRemote: string;
  prRepository: string;
  prBase: string;
  updatedAt: string;
  updatedBy: string;
}

export interface DiscoveryPreview {
  path: string;
  inputPath: string;
  isWorktree: boolean;
  commonDir: string;
  projectId: ID;
  projectName: string;
  branch: string;
  head: string;
  detached: boolean;
  worktrees: Array<{ path: string; head: string; branch: string; detached: boolean; locked: boolean }>;
  remotes: Array<{ name: string; url: string; direction: string }>;
  upstream: string;
  publishRemote: string;
  prRepository: string;
  baseBranch: string;
  prBase: string;
  existingPr: { number: number; url: string; base: string; title: string } | null;
  saved: DiscoveryPreferenceRecord;
  sources: Record<string, string>;
  ambiguities: Array<{ key: string; reason: string; options: string[] }>;
  ready: boolean;
  tools: {
    openCode: { found: boolean; version: string };
    gitHub: { found: boolean; authenticated: boolean; host: string; error: string };
  };
  notes: string[];
}

export interface DiscoveryOpenResult extends DiscoveryPreview {
  workspaceId: ID;
  reusedProject: boolean;
  reusedWorkspace: boolean;
}

export interface RemoteStatus {
  enabled: boolean;
  active: boolean;
  authenticated: boolean;
  user: string;
  csrf: string;
  expiresAt: string;
  publicOrigin: string;
  provider: string;
  identityHeader: string;
  note: string;
}

export interface AppEventEnvelope {
  sequence: number;
  type: string;
  context: Record<string, unknown>;
  summary?: string;
  createdAt?: string;
  workspaceId?: string;
  resync?: boolean;
  after?: number;
}

export interface ReviewCriterion {
  itemId: ID;
  title: string;
  status: 'verified' | 'pending' | 'insufficient_evidence';
  evidence: string;
  acceptanceCriteria: string;
  attemptId: ID;
}

export interface DeliveryCommitRecord {
  id: ID;
  workspaceId: ID;
  batchId?: ID | null;
  attemptId?: ID | null;
  hash: string;
  message: string;
  files: string[];
  headBefore: string;
  headAfter: string;
  status: 'created' | 'failed';
  error: string;
  createdAt: string;
}

export interface DeliveryPushRecord {
  id: ID;
  workspaceId: ID;
  remote: string;
  branch: string;
  upstream: string;
  status: string;
  error: string;
  createdAt: string;
}

export interface DeliveryPullRequest {
  id: ID;
  workspaceId: ID;
  number?: number | null;
  url: string;
  state: string;
  source: string;
  target: string;
  repository: string;
  draft: boolean;
  title: string;
  body: string;
  lastCheckedAt: string;
  createdAt: string;
}

export interface DeliveryState {
  workspaceId: ID;
  branch: string;
  head: string;
  path: string;
  remotes: Array<{ name: string; url: string; direction: string }>;
  ahead: Record<string, number | null>;
  github: { found: boolean; version: string; authenticated: boolean; host: string; error: string };
  writable: boolean;
  commits: DeliveryCommitRecord[];
  pushes: DeliveryPushRecord[];
  pullRequests: DeliveryPullRequest[];
}

export interface DeliveryPreview {
  previewId: ID;
  workspaceId: ID;
  branch: string;
  head: string;
  files: GitFileChange[];
  summary: GitStatusSummary;
  selected: string[];
  stagedOutsideSelection: string[];
  message: string;
  digest: string;
  conflict: boolean;
}

export interface DeliveryPrPreview {
  workspaceId: ID;
  repository: string;
  source: string;
  target: string;
  title: string;
  body: string;
  files: string[];
  existing: Record<string, unknown> | null;
  gh: { found: boolean; authenticated: boolean };
}

export interface DeliveryCreatePrInput {
  workspaceId: ID;
  title: string;
  body: string;
  base: string;
  draft: boolean;
  forceNew?: boolean;
}

export interface ReviewReport {
  workspaceId: ID;
  batchId: ID;
  planVersionId: ID;
  branch: string;
  head: string;
  headAtExecution: string;
  gitChangedSinceExecution: boolean;
  criteria: ReviewCriterion[];
  suggestedSteps: ProposalStep[];
}

export type EventType =
  | 'workspace.changed'
  | 'message.created'
  | 'plan.reviewed'
  | 'queue.generated'
  | 'queue.updated'
  | 'batch.started'
  | 'batch.paused.requested'
  | 'batch.paused.confirmed'
  | 'batch.resumed'
  | 'batch.cancelled'
  | 'batch.completed'
  | 'attempt.started'
  | 'attempt.finished'
  | 'connection.changed';

export interface EventContext {
  workspaceId: ID;
  projectId?: ID;
  batchId?: ID;
  attemptId?: ID;
  conversationId?: ID;
}

export interface AppEvent {
  /** Sequência atribuída pelo backend. No demo, gerada localmente. */
  sequence: number;
  id: ID;
  type: EventType;
  context: EventContext;
  createdAt: string;
  summary: string;
}

export interface WorkspaceState {
  workspace: Workspace;
  project: Project;
  conversation: Conversation;
  plan: Plan;
  batch: Batch | null;
  git: GitInfo;
  connection: ConnectionState;
}

export interface AppSnapshot {
  projects: Project[];
  workspaces: Workspace[];
  activeWorkspaceId: ID;
  conversationsByWorkspace: Record<ID, Conversation>;
  plansByWorkspace: Record<ID, Plan>;
  batchesByWorkspace: Record<ID, Batch[]>;
  attemptsByWorkspace: Record<ID, Attempt[]>;
  gitByWorkspace: Record<ID, GitInfo>;
  connection: ConnectionState;
  events: AppEvent[];
  mode: AppMode;
  apiStatus: ApiStatus;
}

export interface NewProjectInput {
  name: string;
  objective?: string;
  rules?: string;
  baseBranch?: string;
  repoPath?: string;
}

export interface NewWorkspaceInput {
  name: string;
  branch: string;
  baseBranch?: string;
  workDir?: string;
  kind?: string;
}

export interface PlanStepInput {
  id: ID;
  order: number;
  title: string;
  description: string;
  dependencies: ID[];
  acceptanceCriteria: string;
  prompt: string;
  status?: PlanStepStatus;
}

export interface PlanInput {
  objective: string;
  steps: PlanStepInput[];
}

export interface NewQueueItem {
  kind: QueueItemKind;
  title: string;
  content: string;
  fileName?: string;
}
