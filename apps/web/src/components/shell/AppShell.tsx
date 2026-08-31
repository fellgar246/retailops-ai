'use client';

import { useEffect, useState } from 'react';

import { getOverview } from '@/lib/api';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.localStorage.getItem('retailops.sidebar') === 'collapsed',
  );
  const [openReviews, setOpenReviews] = useState<number | null>(null);
  const [environment, setEnvironment] = useState('local');

  useEffect(() => {
    void getOverview()
      .then((overview) => {
        setOpenReviews(overview.reviews.open_cases);
        setEnvironment(overview.environment);
      })
      .catch(() => {
        setOpenReviews(null);
      });
  }, []);

  const toggle = () => {
    setCollapsed((value) => {
      const next = !value;
      window.localStorage.setItem('retailops.sidebar', next ? 'collapsed' : 'expanded');
      return next;
    });
  };

  return (
    <div className={collapsed ? 'shell shell--collapsed' : 'shell'}>
      <Sidebar collapsed={collapsed} onToggle={toggle} openReviews={openReviews} />
      <TopBar environment={environment} />
      <main className="content">
        <div className="content__inner">{children}</div>
      </main>
    </div>
  );
}
