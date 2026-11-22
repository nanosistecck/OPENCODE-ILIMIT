export function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return '--:--';
  }
}

export function formatDateTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return '-';
  }
}

export function shortId(id: string): string {
  return id.length > 14 ? `${id.slice(0, 12)}…` : id;
}
