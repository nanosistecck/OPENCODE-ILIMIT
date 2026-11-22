"""Schemas que espelham os tipos de domínio do frontend (camelCase)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ------------------------------- entrada

class ProjectIn(BaseModel):
    name: str
    objective: str = ""
    rules: str = ""
    baseBranch: str = "main"
    repoPath: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    objective: str | None = None
    rules: str | None = None
    baseBranch: str | None = None
    repoPath: str | None = None


class WorkspaceIn(BaseModel):
    name: str
    branch: str
    baseBranch: str | None = None
    workDir: str = ""
    kind: str = "worktree"


class WorkspacePatch(BaseModel):
    name: str | None = None
    branch: str | None = None
    baseBranch: str | None = None
    workDir: str | None = None
    kind: str | None = None


class MessageIn(BaseModel):
    content: str


class PlanStepIn(BaseModel):
    id: str
    order: int
    title: str
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    acceptanceCriteria: str = ""
    prompt: str = ""
    status: str = "pending"


class PlanIn(BaseModel):
    objective: str = ""
    steps: list[PlanStepIn] = Field(default_factory=list)


class BatchIn(BaseModel):
    name: str | None = None
    title: str | None = None


class NewQueueItemIn(BaseModel):
    kind: str = "prompt"
    title: str = "Prompt"
    content: str
    fileName: str | None = None


class QueueItemPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    fileName: str | None = None


class ReorderIn(BaseModel):
    orderedIds: list[str]


# ------------------------------- saída

class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    objective: str
    rules: str
    baseBranch: str
    repoPath: str | None
    workspaceIds: list[str] = Field(default_factory=list)


class WorkspaceOut(BaseModel):
    id: str
    projectId: str
    name: str
    branch: str
    base: str
    baseBranch: str
    workDir: str
    kind: str
    createdAt: str


class MessageOut(BaseModel):
    id: str
    conversationId: str
    role: str
    content: str
    createdAt: str
    status: str


class ConversationOut(BaseModel):
    id: str
    workspaceId: str
    title: str
    messages: list[MessageOut] = Field(default_factory=list)
    activity: list[dict[str, Any]] = Field(default_factory=list)


class PlanStepOut(BaseModel):
    id: str
    order: int
    title: str
    description: str
    dependencies: list[str]
    acceptanceCriteria: str
    prompt: str
    status: str


class PlanVersionOut(BaseModel):
    id: str
    version: int
    objective: str
    createdAt: str
    steps: list[PlanStepOut]


class PlanOut(BaseModel):
    id: str
    workspaceId: str
    objective: str
    version: int
    status: str
    steps: list[PlanStepOut]
    versions: list[PlanVersionOut] = Field(default_factory=list)


class QueueItemOut(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    fileName: str | None
    order: int
    status: str


class BatchOut(BaseModel):
    id: str
    workspaceId: str
    name: str
    status: str
    pauseRequested: bool = False
    cursor: int
    items: list[QueueItemOut] = Field(default_factory=list)
    sourceVersionId: str | None = None
    createdAt: str


class RepoProbeIn(BaseModel):
    path: str


class RepoLinkIn(BaseModel):
    path: str


class GitCreateIn(BaseModel):
    branch: str
    startRef: str


class GitOpenIn(BaseModel):
    action: str
    path: str = ""
    sourceRef: str = ""
    branch: str = ""


class OpenCodeConfigIn(BaseModel):
    executable: str | None = None
    model: str | None = None
    agent: str | None = None
    timeout: str | None = None


class RetryIn(BaseModel):
    continueSession: bool = False


class ChatMessageIn(BaseModel):
    content: str


class AnalysisIn(BaseModel):
    objective: str = ""


class ProposalIn(BaseModel):
    analysisId: str
    answers: str = ""


class ApproveIn(BaseModel):
    proposalId: str
    objective: str | None = None
    steps: list[dict[str, Any]] | None = None


class AssistantBatchIn(BaseModel):
    versionId: str
    force: bool = False


class DeliveryPreviewIn(BaseModel):
    workspaceId: str
    selectedPaths: list[str] = Field(default_factory=list)
    message: str = ""


class DeliveryCommitIn(BaseModel):
    workspaceId: str
    previewId: str
    selectedPaths: list[str] = Field(default_factory=list)
    message: str
    batchId: str | None = None
    attemptId: str | None = None


class DeliveryPushIn(BaseModel):
    workspaceId: str
    remote: str | None = None
    commitId: str | None = None


class DeliveryPrPreviewIn(BaseModel):
    workspaceId: str
    base: str = ""


class DeliveryPrIn(BaseModel):
    workspaceId: str
    title: str = ""
    body: str = ""
    base: str = ""
    draft: bool = True
    forceNew: bool = False


class DeliveryPrRefreshIn(BaseModel):
    workspaceId: str


class DiscoveryPathIn(BaseModel):
    path: str
    github: bool = True


class DiscoveryOpenIn(BaseModel):
    path: str
    choices: dict[str, Any] = Field(default_factory=dict)


class DiscoveryPreferencesIn(BaseModel):
    projectId: str
    baseBranch: str = ""
    publishRemote: str = ""
    prRepository: str = ""
    prBase: str = ""


class GitOut(BaseModel):
    workspaceId: str
    branch: str
    base: str
    workDir: str
    head: str = ""
    repoRoot: str = ""
    gitStatus: str = "pending"
    linked: bool = False
    registeredOnly: bool = True
    simulated: bool = True
    summary: dict[str, Any] = Field(default_factory=dict)
    files: list[dict[str, Any]] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    verification: dict[str, Any] = Field(default_factory=dict)
    diff: list[dict[str, Any]] = Field(default_factory=list)
    commits: list[dict[str, Any]] = Field(default_factory=list)
    pullRequest: dict[str, Any] = Field(default_factory=dict)


class WorkspaceStateOut(BaseModel):
    workspace: WorkspaceOut
    project: ProjectOut
    conversation: ConversationOut
    plan: PlanOut | None
    batch: BatchOut | None
    git: GitOut
    connection: str = "connected"
