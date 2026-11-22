export type ViewId = 'chat' | 'plan' | 'execution' | 'git' | 'history';

export const VIEW_IDS: ViewId[] = ['chat', 'plan', 'execution', 'git', 'history'];

export const VIEW_LABELS: Record<ViewId, string> = {
  chat: 'Chat',
  plan: 'Plano',
  execution: 'Execução',
  git: 'Git',
  history: 'Histórico',
};
