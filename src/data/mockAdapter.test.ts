import { describe, expect, it } from 'vitest';
import { MockAdapter } from './mockAdapter';
import { AdapterError } from './adapter';
import type { BatchStatus } from '../domain/types';

const WORKSPACE = 'ws-canvas';
const BATCH = 'batch-canvas-demo';

async function waitForStatus(adapter: MockAdapter, status: BatchStatus, timeoutMs = 8000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const batch = adapter.getSnapshot().batchesByWorkspace[WORKSPACE].find((item) => item.id === BATCH);
    if (batch?.status === status) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`Timeout aguardando status ${status}`);
}

function batchOf(adapter: MockAdapter) {
  return adapter.getSnapshot().batchesByWorkspace[WORKSPACE].find((item) => item.id === BATCH)!;
}

async function waitForRunningStep(adapter: MockAdapter, timeoutMs = 4000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (batchOf(adapter).items.some((item) => item.status === 'running')) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error('Timeout aguardando etapa em execução');
}

describe('MockAdapter — execução simulada', () => {
  it('falha na segunda etapa e mantém a terceira pendente', async () => {
    const adapter = new MockAdapter();

    await adapter.startBatch(BATCH);
    await waitForStatus(adapter, 'failed');

    const batch = batchOf(adapter);
    expect(batch.items[0].status).toBe('done');
    expect(batch.items[1].status).toBe('failed');
    expect(batch.items[2].status).toBe('pending');

    const attempts = adapter.getSnapshot().attemptsByWorkspace[WORKSPACE];
    expect(attempts.filter((attempt) => attempt.status === 'failure')).toHaveLength(1);
  });

  it('distingue pausa solicitada de pausa confirmada', async () => {
    const adapter = new MockAdapter();

    await adapter.startBatch(BATCH);
    await waitForRunningStep(adapter);
    await adapter.requestPause(BATCH);
    expect(batchOf(adapter).status).toBe('pausing');
    expect(batchOf(adapter).pauseRequested).toBe(true);

    await waitForStatus(adapter, 'paused');

    expect(batchOf(adapter).status).toBe('paused');
    expect(batchOf(adapter).pauseRequested).toBe(false);
    expect(batchOf(adapter).items[0].status).toBe('done');
    expect(batchOf(adapter).items[1].status).toBe('pending');
  });

  it('retoma a partir da etapa falha após correção do fluxo', async () => {
    const adapter = new MockAdapter();

    await adapter.startBatch(BATCH);
    await waitForStatus(adapter, 'failed');
    await adapter.updateQueueItem(BATCH, 'item-canvas-2', {
      content: 'Dependência corrigida; proseguir com a terceira etapa.',
    });
    await adapter.resumeBatch(BATCH);
    await waitForStatus(adapter, 'completed');

    expect(batchOf(adapter).items.every((item) => item.status === 'done')).toBe(true);
  }, 15000);

  it('troca de espaço não mistura chat, plano, fila e histórico', async () => {
    const adapter = new MockAdapter();

    await adapter.setActiveWorkspace('ws-apis');
    const snapshot = adapter.getSnapshot();

    expect(snapshot.activeWorkspaceId).toBe('ws-apis');
    expect(snapshot.conversationsByWorkspace['ws-apis'].title).toContain('APIs');
    expect(snapshot.plansByWorkspace['ws-apis'].id).toBe('plan-apis');
    expect(snapshot.batchesByWorkspace['ws-apis'][0].id).toBe('batch-apis-1');
    expect(snapshot.attemptsByWorkspace['ws-apis']).toEqual([]);
    expect(snapshot.gitByWorkspace['ws-apis'].branch).toBe('feat/api-config');
  });

  it('desconexão preserva o estado e bloqueia ações do PC', async () => {
    const adapter = new MockAdapter();
    const before = batchOf(adapter).status;

    await adapter.setConnection('disconnected');

    expect(adapter.getSnapshot().connection).toBe('disconnected');
    expect(batchOf(adapter).status).toBe(before);
    await expect(adapter.startBatch(BATCH)).rejects.toBeInstanceOf(AdapterError);
    await expect(adapter.sendMessage(WORKSPACE, 'conv-canvas', 'oi')).rejects.toMatchObject({
      code: 'DISCONNECTED',
    });
  });
});
