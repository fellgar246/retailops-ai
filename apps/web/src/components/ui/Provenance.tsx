import { Badge } from './Badge';

const LABELS = {
  rule: 'Regla determinística',
  ai: 'Interpretación de IA',
  human: 'Decisión humana',
  extracted: 'Valor extraído',
};

interface ProvenanceProps {
  source: keyof typeof LABELS;
}

export function Provenance({ source }: ProvenanceProps) {
  return <Badge kind="provenance" labels={LABELS} value={source} />;
}
