import type { AppSnapshot } from '../domain/types';

/** Snapshot inicial do modo conectado: os dados vêm da API, não de fixtures. */
export function createEmptySnapshot(): AppSnapshot {
  return {
    projects: [],
    workspaces: [],
    activeWorkspaceId: '',
    conversationsByWorkspace: {},
    plansByWorkspace: {},
    batchesByWorkspace: {},
    attemptsByWorkspace: {},
    gitByWorkspace: {},
    connection: 'connected',
    events: [],
    mode: 'connected',
    apiStatus: 'unknown',
  };
}
