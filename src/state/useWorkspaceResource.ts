import { useEffect, useState } from 'react';
import { useAdapter, useSnapshot } from './AppContext';

/**
 * Exercita o estado de carregamento/erro do contrato sem esconder o snapshot
 * já recebido: as telas mostram estados explícitos enquanto a consulta ocorre.
 */
export function useWorkspaceResource() {
  const adapter = useAdapter();
  const workspaceId = useSnapshot().activeWorkspaceId;
  const [state, setState] = useState<{ loading: boolean; error: string | null }>({
    loading: true,
    error: null,
  });

  useEffect(() => {
    if (!workspaceId) {
      setState({ loading: false, error: null });
      return;
    }
    let active = true;
    setState({ loading: true, error: null });
    adapter.getWorkspaceState(workspaceId)
      .then(() => { if (active) setState({ loading: false, error: null }); })
      .catch((error: unknown) => {
        if (active) setState({ loading: false, error: error instanceof Error ? error.message : 'Erro desconhecido' });
      });
    return () => { active = false; };
  }, [adapter, workspaceId]);

  return state;
}
