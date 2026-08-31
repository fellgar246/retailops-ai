'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { isActivePath, NAV_ITEMS } from '@/lib/navigation';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  openReviews: number | null;
}

export function Sidebar({ collapsed, onToggle, openReviews }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span aria-hidden="true" className="sidebar__mark">
          RO
        </span>
        <span className="sidebar__wordmark">RetailOps AI</span>
      </div>
      <nav aria-label="Navegación principal" className="sidebar__nav">
        {NAV_ITEMS.map((item) => {
          const current = isActivePath(pathname, item.href, item.match);
          return (
            <Link
              aria-current={current ? 'page' : undefined}
              className="sidebar__link"
              href={item.href}
              key={item.href}
              title={item.label}
            >
              <span className="sidebar__label">{item.label}</span>
              {item.href === '/reviews' && openReviews ? (
                <span className="sidebar__count">{openReviews}</span>
              ) : null}
            </Link>
          );
        })}
      </nav>
      <div style={{ marginTop: 'auto', padding: 12 }}>
        <button
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expandir menú' : 'Contraer menú'}
          className="icon-btn"
          onClick={onToggle}
          type="button"
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>
    </aside>
  );
}
