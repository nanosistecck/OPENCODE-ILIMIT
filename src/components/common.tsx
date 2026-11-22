import { AlertTriangle, ChevronDown, Inbox, Loader2 } from 'lucide-react';
import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react';

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

/** Rótulos sempre acompanhados de texto: cor nunca é o único sinal. */
const STATUS: Record<string, { label: string; tone: Tone }> = {
  connected: { label: 'Conectado', tone: 'success' },
  connecting: { label: 'Conectando', tone: 'warning' },
  disconnected: { label: 'Desconectado', tone: 'danger' },
  error: { label: 'Erro', tone: 'danger' },
  sent: { label: 'Salvo', tone: 'success' },
  sending: { label: 'Enviando', tone: 'warning' },
  failed: { label: 'Falhou', tone: 'danger' },
  failure: { label: 'Falha', tone: 'danger' },
  done: { label: 'Concluído', tone: 'success' },
  success: { label: 'Sucesso', tone: 'success' },
  completed: { label: 'Concluído', tone: 'success' },
  approved: { label: 'Aprovado', tone: 'success' },
  merged: { label: 'Mesclado', tone: 'success' },
  running: { label: 'Em execução', tone: 'info' },
  in_progress: { label: 'Em andamento', tone: 'info' },
  pausing: { label: 'Pausa solicitada', tone: 'warning' },
  paused: { label: 'Pausado (confirmado)', tone: 'warning' },
  pending: { label: 'Pendente', tone: 'neutral' },
  idle: { label: 'Pronto', tone: 'neutral' },
  draft: { label: 'Rascunho', tone: 'neutral' },
  open: { label: 'Aberto', tone: 'info' },
  in_review: { label: 'Em revisão', tone: 'warning' },
  blocked: { label: 'Bloqueado', tone: 'danger' },
  cancelled: { label: 'Cancelado', tone: 'neutral' },
  skipped: { label: 'Ignorado', tone: 'neutral' },
};

export function statusInfo(status: string): { label: string; tone: Tone } {
  return STATUS[status] ?? { label: status.replace(/_/g, ' '), tone: 'neutral' };
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge--${tone} badge--dot`}>{children}</span>;
}

export function StatusBadge({ status, children }: { status: string; children?: ReactNode }) {
  const info = statusInfo(status);
  return <span className={`badge badge--${info.tone} badge--dot`}>{children ?? info.label}</span>;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'danger';
  small?: boolean;
  block?: boolean;
}

export function Button({ variant = 'default', small, block, className = '', ...rest }: ButtonProps) {
  const classes = [
    'btn',
    variant === 'primary' ? 'btn--primary' : '',
    variant === 'danger' ? 'btn--danger' : '',
    small ? 'btn--sm' : '',
    block ? 'btn--block' : '',
    className,
  ].filter(Boolean).join(' ');
  return <button type="button" className={classes} {...rest} />;
}

export function Collapsible({
  title,
  children,
  defaultOpen = false,
  badge,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  badge?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="collapsible">
      <button
        type="button"
        className="collapsible-trigger"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="row">
          <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms ease' }} />
          {title}
          {badge}
        </span>
      </button>
      {open && <div className="collapsible-content">{children}</div>}
    </div>
  );
}

export function DemoNote({ children }: { children: ReactNode }) {
  return (
    <div className="demo-banner" role="note">
      <AlertTriangle size={16} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty-state">
      <Inbox size={22} aria-hidden="true" />
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <strong>Não foi possível concluir</strong>
      <span>{message}</span>
      {onRetry && <Button small onClick={onRetry}>Tentar novamente</Button>}
    </div>
  );
}

export function LoadingState({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <Loader2 size={20} className="spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="kv">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{children}</span>
    </div>
  );
}
