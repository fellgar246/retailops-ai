import { apiRequest, type Page } from './api-client';
import type {
  AuditPage,
  DocumentDetail,
  DocumentPage,
  ExceptionPage,
  FeedbackRow,
  ForecastPage,
  ForecastRunDetail,
  Job,
  JobKind,
  JobState,
  Overview,
  ReconciliationPage,
  ReconciliationRunDetail,
  ReviewDetail,
  ReviewMetrics,
  ReviewPage,
  SearchResults,
} from './types';

export function getOverview(signal?: AbortSignal): Promise<Overview> {
  return apiRequest<Overview>('/ops/overview', { signal });
}

export function getForecasts(
  query: { limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<ForecastPage> {
  return apiRequest<ForecastPage>('/forecasts', { query, signal });
}

export function getForecast(id: number, signal?: AbortSignal): Promise<ForecastRunDetail> {
  return apiRequest<ForecastRunDetail>(`/forecasts/${id}`, { signal });
}

export function getDocuments(
  query: { status?: string[]; supplier?: string; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<DocumentPage> {
  return apiRequest<DocumentPage>('/documents', { query, signal });
}

export function getDocument(id: number, signal?: AbortSignal): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/documents/${id}`, { signal });
}

export function getReconciliations(
  query: { limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<ReconciliationPage> {
  return apiRequest<ReconciliationPage>('/reconciliations', { query, signal });
}

export function getReconciliation(
  id: number,
  signal?: AbortSignal,
): Promise<ReconciliationRunDetail> {
  return apiRequest<ReconciliationRunDetail>(`/reconciliations/${id}`, { signal });
}

export function getExceptions(
  query: {
    severity?: string[];
    resolution?: string[];
    code?: string;
    limit?: number;
    offset?: number;
  } = {},
  signal?: AbortSignal,
): Promise<ExceptionPage> {
  return apiRequest<ExceptionPage>('/exceptions', { query, signal });
}

export function getReviews(
  query: {
    status?: string[];
    priority?: string[];
    subject_type?: string[];
    risk?: string[];
    supplier?: string;
    limit?: number;
    offset?: number;
  } = {},
  signal?: AbortSignal,
): Promise<ReviewPage> {
  return apiRequest<ReviewPage>('/reviews', { query, signal });
}

export function getReview(id: number, signal?: AbortSignal): Promise<ReviewDetail> {
  return apiRequest<ReviewDetail>(`/reviews/${id}`, { signal });
}

export function getReviewAudit(
  id: number,
  signal?: AbortSignal,
): Promise<{ items: AuditPage['items'] }> {
  return apiRequest<{ items: AuditPage['items'] }>(`/reviews/${id}/audit`, { signal });
}

export function startReview(id: number): Promise<ReviewDetail> {
  return apiRequest<ReviewDetail>(`/reviews/${id}/start`, { method: 'POST', body: {} });
}

export function approveReview(
  id: number,
  body: { comment?: string; snapshot_id?: number },
): Promise<ReviewDetail> {
  return apiRequest<ReviewDetail>(`/reviews/${id}/approve`, { method: 'POST', body });
}

export function rejectReview(
  id: number,
  body: { reason: string; comment?: string },
): Promise<ReviewDetail> {
  return apiRequest<ReviewDetail>(`/reviews/${id}/reject`, { method: 'POST', body });
}

export function correctReview(
  id: number,
  body: { correction: Record<string, unknown>; comment?: string },
): Promise<ReviewDetail> {
  return apiRequest<ReviewDetail>(`/reviews/${id}/correct`, { method: 'POST', body });
}

export function getReviewMetrics(signal?: AbortSignal): Promise<ReviewMetrics> {
  return apiRequest<ReviewMetrics>('/reviews/metrics', { signal });
}

export function getReviewFeedback(
  signal?: AbortSignal,
): Promise<{ items: FeedbackRow[]; count: number }> {
  return apiRequest<{ items: FeedbackRow[]; count: number }>('/reviews/feedback', { signal });
}

export function getAudit(
  query: { limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<AuditPage> {
  return apiRequest<AuditPage>('/audit', { query, signal });
}

export function searchOperations(q: string, signal?: AbortSignal): Promise<SearchResults> {
  return apiRequest<SearchResults>('/search', { query: { q }, signal });
}

export function getJob(id: number, signal?: AbortSignal): Promise<Job> {
  return apiRequest<Job>(`/jobs/${id}`, { signal });
}

export function getJobs(
  query: { kind?: JobKind[]; state?: JobState[]; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<Page<Job>> {
  return apiRequest<Page<Job>>('/jobs', { query, signal });
}

/** Upload a supplier sheet. The response is a job, not the finished work. */
export function uploadSupplierDocument(supplier: string, file: File): Promise<Job> {
  const body = new FormData();
  body.append('supplier', supplier);
  body.append('file', file);
  return apiRequest<Job>('/documents', { method: 'POST', body, isFormData: true });
}

export function startReconciliation(body: {
  supplier: string;
  invoice?: string;
  po?: string;
}): Promise<Job> {
  return apiRequest<Job>('/reconciliations', { method: 'POST', body });
}

export function startForecast(body: {
  horizon?: number;
  min_train_periods?: number;
}): Promise<Job> {
  return apiRequest<Job>('/forecasts', { method: 'POST', body });
}
