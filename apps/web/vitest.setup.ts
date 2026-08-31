import '@testing-library/jest-dom/vitest';

import { createElement, type ReactNode } from 'react';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('next/link', () => ({
  default({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
    className?: string;
    title?: string;
  }) {
    return createElement('a', { href, ...props }, children);
  },
}));

afterEach(() => {
  cleanup();
});
