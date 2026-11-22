import type {
  AppSnapshot,
  Attempt,
  Batch,
  Conversation,
  GitInfo,
  Plan,
  Project,
  Workspace,
} from '../domain/types';

/**
 * Único lugar que contém dados de exemplo. As telas NÃO importam este arquivo:
 * todo acesso passa por `Adapter`.
 */

const T0 = '2026-11-20T09:00:00.000Z';
const T1 = '2026-11-20T09:04:00.000Z';
const T2 = '2026-11-20T09:11:00.000Z';
const T3 = '2026-11-20T10:02:00.000Z';

export const PROJECTS: Project[] = [
  {
    id: 'prj-nia',
    name: 'NIA',
    description: 'Plataforma de conhecimento e automação',
    baseBranch: 'main',
    workspaceIds: ['ws-main', 'ws-canvas', 'ws-apis'],
  },
];

export const WORKSPACES: Workspace[] = [
  {
    id: 'ws-main',
    projectId: 'prj-nia',
    name: 'Base principal',
    branch: 'main',
    base: 'main',
    kind: 'base',
    createdAt: T0,
  },
  {
    id: 'ws-canvas',
    projectId: 'prj-nia',
    name: 'Canvas infinito',
    branch: 'feat/infinite-canvas',
    base: 'main',
    kind: 'worktree',
    createdAt: T1,
  },
  {
    id: 'ws-apis',
    projectId: 'prj-nia',
    name: 'Configuração de APIs',
    branch: 'feat/api-config',
    base: 'main',
    kind: 'worktree',
    createdAt: T2,
  },
];

export const CONVERSATIONS: Record<string, Conversation> = {
  'ws-main': {
    id: 'conv-main',
    workspaceId: 'ws-main',
    title: 'Contexto da base',
    messages: [
      {
        id: 'msg-main-1',
        conversationId: 'conv-main',
        role: 'user',
        content: 'Qual é o estado atual da base main?',
        createdAt: T0,
        status: 'sent',
      },
      {
        id: 'msg-main-2',
        conversationId: 'conv-main',
        role: 'assistant',
        content: 'Base estável. Dois worktrees ativos: canvas infinito e configuração de APIs.',
        createdAt: T1,
        status: 'sent',
      },
    ],
    activity: [
      { id: 'act-main-1', label: 'Ler estrutura do projeto', detail: 'package.json, tsconfig', status: 'done', createdAt: T0 },
    ],
  },
  'ws-canvas': {
    id: 'conv-canvas',
    workspaceId: 'ws-canvas',
    title: 'Canvas infinito — discussão',
    messages: [
      {
        id: 'msg-canvas-1',
        conversationId: 'conv-canvas',
        role: 'user',
        content: 'Como vamos lidar com o pan/zoom em 360px?',
        createdAt: T1,
        status: 'sent',
      },
      {
        id: 'msg-canvas-2',
        conversationId: 'conv-canvas',
        role: 'assistant',
        content: 'Mantemos gestos de pinça e uma barra compacta. O zoom mínimo precisa preservar os controles.',
        createdAt: T2,
        status: 'sent',
      },
    ],
    activity: [
      { id: 'act-canvas-1', label: 'Inspecionar viewport', detail: '360 × 740', status: 'done', createdAt: T1 },
      { id: 'act-canvas-2', label: 'Ajustar transformação', detail: 'matriz de zoom', status: 'done', createdAt: T2 },
    ],
  },
  'ws-apis': {
    id: 'conv-apis',
    workspaceId: 'ws-apis',
    title: 'Configuração de APIs — discussão',
    messages: [
      {
        id: 'msg-apis-1',
        conversationId: 'conv-apis',
        role: 'user',
        content: 'O contrato HTTP já está definido?',
        createdAt: T2,
        status: 'sent',
      },
      {
        id: 'msg-apis-2',
        conversationId: 'conv-apis',
        role: 'assistant',
        content: 'Caminhos relativos definidos; transporte WebSocket fica para a integração real.',
        createdAt: T3,
        status: 'sent',
      },
    ],
    activity: [
      { id: 'act-apis-1', label: 'Listar endpoints', detail: '6 rotas', status: 'done', createdAt: T2 },
    ],
  },
};

export const PLANS: Record<string, Plan> = {
  'ws-main': {
    id: 'plan-main',
    workspaceId: 'ws-main',
    objective: 'Manter a base main estável e pronta para integração.',
    version: 1,
    status: 'approved',
    versions: [],
    steps: [
      {
        id: 'step-main-1', order: 1, title: 'Auditar dependências',
        description: 'Revisar o-lock e versões mínimas.',
        dependencies: [], acceptanceCriteria: 'Nenhuma dependência sem versão fixa.', status: 'done',
      },
      {
        id: 'step-main-2', order: 2, title: 'Congelar contrato',
        description: 'Fixar os tipos de domínio compartilhados.',
        dependencies: ['step-main-1'],
        acceptanceCriteria: 'Tipos exportados e sem ' + 'any' + '.', status: 'done',
      },
    ],
  },
  'ws-canvas': {
    id: 'plan-canvas',
    workspaceId: 'ws-canvas',
    objective: 'Entregar um canvas infinito navegável em desktop e em 360 px.',
    version: 2,
    status: 'draft',
    versions: [
      {
        version: 1,
        objective: 'Protótipo de canvas infinito.',
        createdAt: T1,
        steps: [
          {
            id: 'step-canvas-v1-1', order: 1, title: 'Protótipo',
            description: 'Renderizar grade.',
            dependencies: [], acceptanceCriteria: 'Grid visível.', status: 'done',
          },
        ],
      },
    ],
    steps: [
      {
        id: 'step-canvas-1', order: 1, title: 'Modelo de câmera',
        description: 'Definir origem, escala e limites de zoom para o workspace.',
        dependencies: [], acceptanceCriteria: 'Zoom entre 0.25 e 4 sem perder os controles.', status: 'done',
      },
      {
        id: 'step-canvas-2', order: 2, title: 'Interação por ponteiro',
        description: 'Pan com arraste e zoom com roda/pinça.',
        dependencies: ['step-canvas-1'],
        acceptanceCriteria: 'Gesto contínuo em desktop e touch, sem scroll horizontal.', status: 'in_progress',
      },
      {
        id: 'step-canvas-3', order: 3, title: 'Persistência da viewport',
        description: 'Salvar e restaurar a posição por workspace.',
        dependencies: ['step-canvas-2'],
        acceptanceCriteria: 'Recarregar preserva a última câmera.', status: 'pending',
      },
    ],
  },
  'ws-apis': {
    id: 'plan-apis',
    workspaceId: 'ws-apis',
    objective: 'Definir o contrato de integração com o backend FastAPI.',
    version: 1,
    status: 'draft',
    versions: [],
    steps: [
      {
        id: 'step-apis-1', order: 1, title: 'Mapear entidades',
        description: 'Projeto, espaço, lote e tentativa com IDs estáveis.',
        dependencies: [], acceptanceCriteria: 'IDs documentados e reutilizados.', status: 'done',
      },
      {
        id: 'step-apis-2', order: 2, title: 'Definir eventos',
        description: 'Contexto, tipo e sequência atribuída pelo backend.',
        dependencies: ['step-apis-1'], acceptanceCriteria: 'Eventos versionados com sequence.', status: 'pending',
      },
      {
        id: 'step-apis-3', order: 3, title: 'Reservar WebSocket',
        description: 'Transporte real na integração.',
        dependencies: ['step-apis-2'], acceptanceCriteria: 'Reconexção preserva último estado.', status: 'pending',
      },
    ],
  },
};

function makeBatch(
  id: string,
  workspaceId: string,
  name: string,
  createdAt: string,
  items: Array<{ id: string; kind: 'prompt' | 'file'; title: string; content: string; fileName?: string }>,
): Batch {
  return {
    id,
    workspaceId,
    name,
    createdAt,
    status: 'idle',
    pauseRequested: false,
    cursor: 0,
    items: items.map((item, index) => ({ ...item, order: index, status: 'pending' })),
  };
}

export const BATCHES: Record<string, Batch[]> = {
  'ws-main': [
    makeBatch('batch-main-1', 'ws-main', 'Verificação da base', T0, [
      { id: 'item-main-1', kind: 'prompt', title: 'Checar build', content: 'Rodar typecheck e build da base.' },
      { id: 'item-main-2', kind: 'file', title: 'README', content: 'Conteúdo do README', fileName: 'README.md' },
    ]),
  ],
  'ws-canvas': [
    makeBatch('batch-canvas-demo', 'ws-canvas', 'Canvas — lote de demonstração', T1, [
      {
        id: 'item-canvas-1', kind: 'prompt', title: 'Gerar modelo de câmera',
        content: 'Implemente o modelo de câmera com limites de zoom de 0.25 a 4.',
      },
      {
        id: 'item-canvas-2', kind: 'file', title: 'Especificação de gestos',
        content: 'Gestos de pan e pinça devem funcionar em 360px.\nFalha simulada: dependência ausente.',
        fileName: 'gestos.md',
      },
      {
        id: 'item-canvas-3', kind: 'prompt', title: 'Persistir viewport',
        content: 'Salve a câmera por workspace e restaure ao reabrir.',
      },
    ]),
  ],
  'ws-apis': [
    makeBatch('batch-apis-1', 'ws-apis', 'Contrato de API', T2, [
      { id: 'item-apis-1', kind: 'prompt', title: 'Listar rotas', content: 'Documentar rotas relativas /api.' },
      { id: 'item-apis-2', kind: 'file', title: 'Eventos', content: 'eventos.md', fileName: 'eventos.txt' },
    ]),
  ],
};

export const ATTEMPTS: Record<string, Attempt[]> = {
  'ws-main': [],
  'ws-canvas': [
    {
      id: 'attempt-canvas-old', batchId: 'batch-canvas-demo', workspaceId: 'ws-canvas',
      itemId: 'item-canvas-1', itemTitle: 'Gerar modelo de câmera', stepIndex: 0,
      prompt: 'Implemente o modelo de câmera com limites de zoom de 0.25 a 4.',
      output: '[ok] camera.ts criado\n[ok] limites aplicados',
      result: 'Sucesso na execução anterior.', status: 'success',
      branch: 'feat/infinite-canvas', workspaceRef: 'ws-canvas',
      startedAt: T1, finishedAt: T2,
    },
  ],
  'ws-apis': [],
};

function makeGit(
  workspaceId: string,
  branch: string,
  base: string,
  diff: GitInfo['diff'],
  commits: GitInfo['commits'],
  pr: GitInfo['pullRequest'],
): GitInfo {
  return { workspaceId, branch, base, diff, commits, pullRequest: pr, simulated: true };
}

export const GIT: Record<string, GitInfo> = {
  'ws-main': makeGit(
    'ws-main', 'main', 'main',
    [
      { kind: 'meta', content: 'diff --git a/src/domain/types.ts b/src/domain/types.ts' },
      { kind: 'context', content: '  export interface Workspace {' },
      { kind: 'add', content: '+  branch: string; // exibição' },
      { kind: 'context', content: '  }' },
    ],
    [
      { id: 'c-main-1', hash: 'a1b2c3d', message: 'fix: estabilizar base', author: 'NIA Bot', createdAt: T0 },
    ],
    {
      id: 'pr-main-1', title: 'Base estável', source: 'main', target: 'release', status: 'merged',
      verifications: [
        { id: 'v-main-1', name: 'typecheck', status: 'success', conclusion: 'passou' },
      ],
    },
  ),
  'ws-canvas': makeGit(
    'ws-canvas', 'feat/infinite-canvas', 'main',
    [
      { kind: 'meta', content: 'diff --git a/src/features/canvas.tsx b/src/features/canvas.tsx' },
      { kind: 'meta', content: '--- a/src/features/canvas.tsx' },
      { kind: 'meta', content: '+++ b/src/features/canvas.tsx' },
      { kind: 'context', content: ' const Camera = {' },
      { kind: 'add', content: '+  minZoom: 0.25,' },
      { kind: 'add', content: '+  maxZoom: 4,' },
      { kind: 'remove', content: '-  minZoom: 1,' },
      { kind: 'context', content: ' };' },
    ],
    [
      { id: 'c-canvas-2', hash: 'f6e5d4c', message: 'feat: limite de zoom', author: 'OpenCode', createdAt: T2 },
      { id: 'c-canvas-1', hash: 'b4a9f10', message: 'feat: grade infinita', author: 'OpenCode', createdAt: T1 },
    ],
    {
      id: 'pr-canvas-1', title: 'Canvas infinito: câmera e gestos', source: 'feat/infinite-canvas', target: 'main', status: 'open',
      verifications: [
        { id: 'v-canvas-1', name: 'typecheck', status: 'success', conclusion: 'passou' },
        { id: 'v-canvas-2', name: 'build', status: 'success', conclusion: 'passou' },
        { id: 'v-canvas-3', name: 'testes 360px', status: 'pending', conclusion: 'aguardando execução' },
      ],
    },
  ),
  'ws-apis': makeGit(
    'ws-apis', 'feat/api-config', 'main',
    [
      { kind: 'meta', content: 'diff --git a/docs/api-contract.md b/docs/api-contract.md' },
      { kind: 'add', content: '+GET /api/projects' },
      { kind: 'add', content: '+POST /api/workspaces/:id/messages' },
    ],
    [
      { id: 'c-apis-1', hash: '9c8d7e6', message: 'docs: contrato HTTP', author: 'OpenCode', createdAt: T2 },
    ],
    {
      id: 'pr-apis-1', title: 'Contrato de integração', source: 'feat/api-config', target: 'main', status: 'draft',
      verifications: [
        { id: 'v-apis-1', name: 'revisão de contrato', status: 'pending', conclusion: 'aguardando revisão' },
      ],
    },
  ),
};

export function createInitialSnapshot(): AppSnapshot {
  return {
    projects: structuredClone(PROJECTS),
    workspaces: structuredClone(WORKSPACES),
    activeWorkspaceId: 'ws-canvas',
    conversationsByWorkspace: structuredClone(CONVERSATIONS),
    plansByWorkspace: structuredClone(PLANS),
    batchesByWorkspace: structuredClone(BATCHES),
    attemptsByWorkspace: structuredClone(ATTEMPTS),
    gitByWorkspace: structuredClone(GIT),
    connection: 'connected',
    events: [],
    mode: 'demo',
    apiStatus: 'unknown',
  };
}
