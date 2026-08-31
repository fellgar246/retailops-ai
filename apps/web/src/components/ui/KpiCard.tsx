import Link from 'next/link';

interface KpiCardProps {
  label: string;
  value: string;
  meta: string;
  href: string;
}

export function KpiCard({ label, value, meta, href }: KpiCardProps) {
  return (
    <Link className="kpi" href={href}>
      <p className="kpi__label">{label}</p>
      <p className="kpi__value tabular">{value}</p>
      <p className="kpi__meta">{meta}</p>
    </Link>
  );
}
