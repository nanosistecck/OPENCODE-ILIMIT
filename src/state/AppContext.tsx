import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { HttpAdapter } from '../data/httpAdapter';
import { MockAdapter } from '../data/mockAdapter';
import type { ExtendedAdapter } from '../data/adapter';
import type { AppMode, AppSnapshot, Theme } from '../domain/types';

const AdapterContext = createContext<ExtendedAdapter | null>(null);

interface ThemeValue {
  theme: Theme;
  toggleTheme: () => void;
}

interface ModeValue {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);
const ModeContext = createContext<ModeValue | null>(null);

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const saved = localStorage.getItem(key);
    if (saved && (allowed as readonly string[]).includes(saved)) return saved as T;
  } catch {
    // localStorage pode ser bloqueado
  }
  return fallback;
}

function readInitialTheme(): Theme {
  const stored = readStored<Theme>('oc-ilimit-theme', ['light', 'dark'], 'dark');
  if (stored !== 'dark') return stored;
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

export function AppProvider({ children }: { children: ReactNode }) {
  const mockRef = useRef<MockAdapter | null>(null);
  const httpRef = useRef<HttpAdapter | null>(null);
  if (mockRef.current === null) mockRef.current = new MockAdapter();
  if (httpRef.current === null) httpRef.current = new HttpAdapter();
  const mock = mockRef.current;
  const http = httpRef.current;

  const [mode, setModeState] = useState<AppMode>(() =>
    readStored<AppMode>('oc-ilimit-mode', ['demo', 'connected'], 'connected'),
  );
  const adapter: ExtendedAdapter = mode === 'demo' ? mock : http;

  const setMode = useCallback((next: AppMode) => {
    setModeState(next);
    try {
      localStorage.setItem('oc-ilimit-mode', next);
    } catch {
      // preferência salva é best-effort
    }
  }, []);

  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      localStorage.setItem('oc-ilimit-theme', theme);
    } catch {
      // preferência salva é best-effort
    }
  }, [theme]);

  useEffect(() => {
    if (mode !== 'connected') return;
    void http.getHealth().catch(() => undefined);
    void http.refresh().catch(() => undefined);
  }, [http, mode]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  const themeValue = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  const modeValue = useMemo(() => ({ mode, setMode }), [mode, setMode]);

  return (
    <AdapterContext.Provider value={adapter}>
      <ModeContext.Provider value={modeValue}>
        <ThemeContext.Provider value={themeValue}>{children}</ThemeContext.Provider>
      </ModeContext.Provider>
    </AdapterContext.Provider>
  );
}

export function useAdapter(): ExtendedAdapter {
  const adapter = useContext(AdapterContext);
  if (!adapter) throw new Error('useAdapter deve ser usado dentro de AppProvider');
  return adapter;
}

export function useSnapshot(): AppSnapshot {
  const adapter = useAdapter();
  return useSyncExternalStore(adapter.subscribe, adapter.getSnapshot, adapter.getSnapshot);
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme deve ser usado dentro de AppProvider');
  return value;
}

export function useMode(): ModeValue {
  const value = useContext(ModeContext);
  if (!value) throw new Error('useMode deve ser usado dentro de AppProvider');
  return value;
}
