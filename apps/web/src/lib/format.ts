const NUMBER = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 });
const MONEY = new Intl.NumberFormat('es-MX', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const PERCENT = new Intl.NumberFormat('es-MX', {
  style: 'percent',
  maximumFractionDigits: 1,
});
const DATE = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' });
const DATETIME = new Intl.DateTimeFormat('es-MX', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return NUMBER.format(value);
}

export function formatMoney(value: string | number | null | undefined, currency = 'MXN'): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const amount = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(amount)) {
    return String(value);
  }
  return `${currency} ${MONEY.format(amount)}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return PERCENT.format(value);
}

export function formatConfidence(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return 'Sin confianza';
  }
  const amount = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(amount)) {
    return String(value);
  }
  return PERCENT.format(amount);
}

export function confidenceBand(
  value: string | number | null | undefined,
): 'alta' | 'media' | 'baja' | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const amount = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(amount)) {
    return null;
  }
  if (amount >= 0.8) {
    return 'alta';
  }
  if (amount >= 0.5) {
    return 'media';
  }
  return 'baja';
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return DATE.format(parsed);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return DATETIME.format(parsed);
}

export function formatRelative(value: string | null | undefined, now = Date.now()): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const delta = now - parsed.getTime();
  const minutes = Math.round(delta / 60_000);
  if (Math.abs(minutes) < 1) {
    return 'hace un momento';
  }
  if (Math.abs(minutes) < 60) {
    return `hace ${Math.abs(minutes)} min`;
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return `hace ${Math.abs(hours)} h`;
  }
  return formatDateTime(value);
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return '—';
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} s`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} min`;
  }
  return `${(seconds / 3600).toFixed(1)} h`;
}
