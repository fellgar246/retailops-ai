export const NAV_ITEMS = [
  { href: '/', label: 'Overview', match: 'exact' as const },
  { href: '/reviews', label: 'Revisiones', match: 'prefix' as const },
  { href: '/forecasts', label: 'Pronósticos', match: 'prefix' as const },
  { href: '/documents', label: 'Documentos de proveedor', match: 'prefix' as const },
  { href: '/reconciliations', label: 'Conciliaciones', match: 'prefix' as const },
  { href: '/evaluation', label: 'Evaluación de IA', match: 'prefix' as const },
  { href: '/audit', label: 'Auditoría', match: 'prefix' as const },
  { href: '/settings', label: 'Configuración', match: 'prefix' as const },
] as const;

export function isActivePath(
  pathname: string | null | undefined,
  href: string,
  match: 'exact' | 'prefix',
): boolean {
  if (!pathname) {
    return false;
  }
  if (match === 'exact') {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
