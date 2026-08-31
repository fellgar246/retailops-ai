import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumb?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, breadcrumb, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__copy">
        {breadcrumb ? <p className="breadcrumb">{breadcrumb}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}
