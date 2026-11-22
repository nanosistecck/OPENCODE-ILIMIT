import {
  createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode,
} from 'react';
import { useAdapter, useSnapshot } from '../state/AppContext';
import type { AppEventEnvelope, RemoteStatus } from '../domain/types';

interface RemoteValue {
  status: RemoteStatus | null;
  connected: boolean;
  lastSequence: number;
  lastUpdated: Date | null;
  error: string;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const RemoteContext = createContext<RemoteValue | null>(null);

const seqKey = (workspaceId: string) => `oc-events-${workspaceId}`;

export function RemoteProvider({ children }: { children: ReactNode }) {
  const adapter = useAdapter();
  const { activeWorkspaceId } = useSnapshot();
  const [status, setStatus] = useState<RemoteStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastSequence, setLastSequence] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const seqRef = useRef(0);

  const loadStatus = useCallback(async () => {
    try {
      const next = await adapter.getRemoteStatus();
      setStatus(next);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao consultar o modo remoto.');
      return null;
    }
  }, [adapter]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    const myGeneration = ++generation.current;
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let active = true;

    if (!activeWorkspaceId) return;

    const start = async () => {
      const current = status ?? await loadStatus();
      if (!active || myGeneration !== generation.current) return;
      if (current?.active && !current.authenticated) {
        setConnected(false);
        return;
      }

      const stored = Number(localStorage.getItem(seqKey(activeWorkspaceId)) ?? 0);
      seqRef.current = stored;
      setLastSequence(stored);
      try {
        const initial = await adapter.getEvents(activeWorkspaceId, stored);
        if (!active || myGeneration !== generation.current) return;
        const nextSeq = Math.max(stored, initial.sequence);
        seqRef.current = nextSeq;
        setLastSequence(nextSeq);
        localStorage.setItem(seqKey(activeWorkspaceId), String(nextSeq));
        setLastUpdated(new Date());
        if (initial.resync) await adapter.refresh();
        window.dispatchEvent(new CustomEvent('oc-remote-change'));
      } catch {
        // A consulta HTTP pode falhar se a rede cair; o WebSocket tentará novamente.
      }

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${location.host}/ws/events?workspaceId=${encodeURIComponent(activeWorkspaceId)}&after=${seqRef.current}`;
      socket = new WebSocket(url);
      socket.onopen = () => {
        if (!active) return;
        setConnected(true);
        setError('');
      };
      socket.onmessage = (event) => {
        if (!active || myGeneration !== generation.current) return;
        try {
          const data = JSON.parse(event.data as string) as AppEventEnvelope;
          const seq = Number(data.sequence ?? 0);
          if (seq > 0 && seq <= seqRef.current && data.type !== 'snapshot') return; // duplicata/antiga
          if (seq > 0) {
            seqRef.current = seq;
            setLastSequence(seq);
            localStorage.setItem(seqKey(activeWorkspaceId), String(seq));
          }
          setLastUpdated(new Date());
          if (data.type === 'resync' || data.resync || data.type === 'snapshot') {
            void adapter.refresh();
          }
          window.dispatchEvent(new CustomEvent('oc-remote-change'));
        } catch {
          // evento ignorado
        }
      };
      socket.onclose = () => {
        if (!active || myGeneration !== generation.current) return;
        setConnected(false);
        timer = window.setTimeout(() => { void start(); }, 1500);
      };
      socket.onerror = () => {
        setError('Conexão em tempo real indisponível; reconectando.');
      };
    };

    void start();
    return () => {
      active = false;
      generation.current++;
      if (timer) window.clearTimeout(timer);
      socket?.close();
    };
  }, [adapter, activeWorkspaceId, loadStatus, status?.active, status?.authenticated]);

  useEffect(() => {
    document.body.classList.toggle('remote-offline', !!status?.active && !!status.authenticated && !connected);
    return () => document.body.classList.remove('remote-offline');
  }, [status?.active, status?.authenticated, connected]);

  const login = useCallback(async (password: string) => {
    setError('');
    try {
      const next = await adapter.remoteLogin(password);
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no login.');
    }
  }, [adapter]);

  const logout = useCallback(async () => {
    await adapter.remoteLogout();
    setStatus((current) => current ? { ...current, authenticated: false, csrf: '', user: '' } : current);
    setConnected(false);
  }, [adapter]);

  return (
    <RemoteContext.Provider value={{ status, connected, lastSequence, lastUpdated, error, login, logout }}>
      {children}
    </RemoteContext.Provider>
  );
}

export function useRemote(): RemoteValue {
  const value = useContext(RemoteContext);
  if (!value) throw new Error('useRemote deve ser usado dentro de RemoteProvider');
  return value;
}
