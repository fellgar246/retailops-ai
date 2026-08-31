import { labelOf } from '@/lib/labels';

interface BadgeProps {
  kind: 'status' | 'severity' | 'priority' | 'risk' | 'ai' | 'provenance' | 'neutral';
  value: string;
  labels?: Record<string, string>;
}

export function Badge({ kind, value, labels }: BadgeProps) {
  const text = labels ? labelOf(labels, value) : value;
  return <span className={`badge badge--${kind} badge--${kind}-${value}`}>{text}</span>;
}
