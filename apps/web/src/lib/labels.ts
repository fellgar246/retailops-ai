import type { ForecastStatus, ReviewPriority, ReviewStatus, RiskLevel, Severity } from './types';

export const STATUS_LABELS: Record<ReviewStatus, string> = {
  open: 'Pendiente',
  in_review: 'En revisión',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  corrected: 'Corregido',
  cancelled: 'Cancelado',
};

export const PRIORITY_LABELS: Record<ReviewPriority, string> = {
  urgent: 'Urgente',
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  error: 'Alta',
  warning: 'Media',
  info: 'Informativa',
};

export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  received: 'Recibido',
  parsed: 'Extraído',
  parse_failed: 'Falló la extracción',
  validated: 'Validado',
  review_ready: 'Listo para revisión',
};

export const FORECAST_STATUS_LABELS: Record<ForecastStatus, string> = {
  evaluated: 'Evaluado',
  projected: 'Proyectado',
};

export const SUBJECT_LABELS: Record<string, string> = {
  document_finding: 'Hallazgo de documento',
  reconciliation_exception: 'Excepción de conciliación',
};

export const EVENT_LABELS: Record<string, string> = {
  created: 'Creado',
  opened: 'Abierto',
  assigned: 'Asignado',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  corrected: 'Corregido',
  status_changed: 'Cambio de estado',
};

export const ACTION_LABELS: Record<string, string> = {
  accept: 'Aceptar',
  request_correction: 'Solicitar corrección',
  escalate: 'Escalar',
  hold_payment: 'Retener pago',
  no_action: 'Sin acción',
  human_review: 'Revisión humana',
};

export const RESOLUTION_LABELS: Record<string, string> = {
  open: 'Abierta',
  resolved: 'Resuelta',
  dismissed: 'Descartada',
};

export const ENVIRONMENT_LABELS: Record<string, string> = {
  local: 'Local',
  development: 'Desarrollo',
  staging: 'Staging',
  production: 'Producción',
};

export function labelOf(map: Record<string, string>, value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  return map[value] ?? value.replaceAll('_', ' ');
}
