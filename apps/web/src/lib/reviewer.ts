export const REVIEWER_STORAGE_KEY = 'retailops.reviewer';
export const DEFAULT_REVIEWER = 'analista';

export function readReviewer(): string {
  if (typeof window === 'undefined') {
    return DEFAULT_REVIEWER;
  }
  return window.localStorage.getItem(REVIEWER_STORAGE_KEY)?.trim() || DEFAULT_REVIEWER;
}

export function writeReviewer(value: string): string {
  const reviewer = value.trim() || DEFAULT_REVIEWER;
  window.localStorage.setItem(REVIEWER_STORAGE_KEY, reviewer);
  return reviewer;
}
