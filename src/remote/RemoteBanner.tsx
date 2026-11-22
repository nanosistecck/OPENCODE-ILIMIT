import { LogOut, Radio, Wifi, WifiOff } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button } from '../components/common';
import { formatTime } from '../utils/format';
import { useRemote } from './RemoteProvider';

export function RemoteBanner() {
  const { status, connected, lastSequence, lastUpdated, error, login, logout } = useRemote();
  const [password, setPassword] = useState('');

  if (!status?.active) {
    return (
      <p className="panel-subtle">
        <Radio size={12} aria-hidden="true" /> Acesso remoto desativado no PC.
      </p>
    );
  }

  if (!status.authenticated) {
    return (
      <div className="demo-banner" role="alert">
        <WifiOff size={16} aria-hidden="true" />
        <span>Acesso remoto requer login.</span>
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            void login(password);
            setPassword('');
          }}
        >
          <label className="sr-only" htmlFor="remote-password">Senha remota</label>
          <input
            id="remote-password"
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Senha configurada no PC"
          />
          <Button variant="primary" type="submit" disabled={!password}>Entrar</Button>
        </form>
        {error && <span>{error}</span>}
      </div>
    );
  }

  return (
    <div className="panel-subtle remote-status" role="status">
      <Badge tone={connected ? 'success' : 'warning'}>
        {connected ? <Wifi size={12} aria-hidden="true" /> : <WifiOff size={12} aria-hidden="true" />}
        {connected ? 'Tempo real conectado' : 'Reconectando…'}
      </Badge>
      <span>
        {status.user || 'remoto'} · sequência #{lastSequence}
        {lastUpdated ? ` · atualizado às ${formatTime(lastUpdated.toISOString())}` : ''}
        {status.publicOrigin ? ` · ${status.publicOrigin}` : ''}
      </span>
      {error && <span>{error}</span>}
      <Button small onClick={() => void logout()}>
        <LogOut size={13} aria-hidden="true" /> Sair
      </Button>
    </div>
  );
}
