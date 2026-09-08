'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { LoadingState } from '@/components/ui/LoadingState';
import { getOverview } from '@/lib/api';
import { useSession } from '@/lib/use-session';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

//: Rendered without the operations shell, because reaching it means there is
//: no session to frame.
const PUBLIC_PATHS = ['/signin'];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, loading } = useSession();
  const isPublic = PUBLIC_PATHS.includes(pathname ?? '');
  const signedIn = Boolean(session?.user);

  const [collapsed, setCollapsed] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.localStorage.getItem('retailops.sidebar') === 'collapsed',
  );
  const [openReviews, setOpenReviews] = useState<number | null>(null);
  const [environment, setEnvironment] = useState('local');

  useEffect(() => {
    if (!loading && !signedIn && !isPublic) {
      router.replace('/signin');
    }
  }, [loading, signedIn, isPublic, router]);

  useEffect(() => {
    if (!signedIn) {
      return;
    }
    void getOverview()
      .then((overview) => {
        setOpenReviews(overview.reviews.open_cases);
        setEnvironment(overview.environment);
      })
      .catch(() => {
        setOpenReviews(null);
      });
  }, [signedIn]);

  const toggle = () => {
    setCollapsed((value) => {
      const next = !value;
      window.localStorage.setItem('retailops.sidebar', next ? 'collapsed' : 'expanded');
      return next;
    });
  };

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading || !signedIn) {
    // Never frame a page with data that a missing session cannot back.
    return <LoadingState label="Comprobando la sesión…" />;
  }

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
