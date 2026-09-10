import type { Page } from './api-client';

export type Severity = 'error' | 'warning' | 'info';
export type ReviewStatus =
  'open' | 'in_review' | 'approved' | 'rejected' | 'corrected' | 'cancelled';
export type ReviewPriority = 'low' | 'medium' | 'high' | 'urgent';
export type RiskLevel = 'low' | 'medium' | 'high';
export type ForecastStatus = 'evaluated' | 'projected';

export interface ForecastMetrics {
  mae?: number;
  rmse?: number;
  wape?: number;
  bias?: number;
}

export interface ForecastRunSummary {
  id: number;
  model_id: string;
  model_version: string | null;
  generated_at: string;
  cutoff: string;
  horizon: number;
  problem_id: string;
  status: ForecastStatus;
  prediction_count: number;
  metrics: ForecastMetrics | null;
}

export interface ForecastPrediction {
  store_code: string;
  category_code: string;
  period_start: string;
  step: number;
  predicted: number;
  actual: number | null;
}

export interface ForecastRunDetail extends ForecastRunSummary {
  run_metadata: Record<string, unknown> | null;
  predictions: ForecastPrediction[];
}

export interface SeveritySummary {
  error: number;
  warning: number;
  info: number;
}

export interface DocumentSummary {
  id: number;
  supplier_id: number;
  supplier_code: string | null;
  supplier_name: string | null;
  filename: string;
  media_type: string;
  status: string;
  finding_count: number;
  severity_summary: SeveritySummary;
  processed_at: string;
  created_at: string;
}

export interface DocumentFinding {
  id: number;
  code: string;
  field: string | null;
  row_reference: number | null;
  severity: Severity;
  message: string;
  proposed_value: string | null;
  created_at: string;
  provenance: 'rule';
}

export interface DocumentRow {
  row_number: number;
  supplier_sku: string | null;
  ean: string | null;
  description: string | null;
  category: string | null;
  cost: string | null;
  vat: string | null;
  case_pack: number | null;
  minimum_order_quantity: number | null;
  lead_time_days: number | null;
  invalid_fields: string[];
  provenance: 'extracted';
}

export interface DocumentDetail extends DocumentSummary {
  checksum: string;
  storage_key: string;
  document_type: string;
  findings: DocumentFinding[];
  review_cases: ReviewCase[];
  rows: DocumentRow[];
  rows_available: boolean;
}

export interface DocumentRef {
  id: number;
  number: string;
}

export interface ProductRef {
  id: number;
  sku: string;
  name: string;
}

export interface ReconciliationException {
  id: number;
  reconciliation_run_id: number;
  code: string;
  severity: Severity;
  expected_value: string;
  actual_value: string;
  financial_impact: string;
  resolution_status: string;
  message: string;
  purchase_order: DocumentRef | null;
  goods_receipt: DocumentRef | null;
  supplier_invoice: DocumentRef | null;
  product: ProductRef | null;
  review_case_id: number | null;
  review_status: ReviewStatus | null;
  provenance: 'rule';
  created_at: string;
}

export interface ReconciliationRunSummary {
  id: number;
  scope_key: string;
  version: number;
  generated_at: string;
  purchase_order_count: number;
  goods_receipt_count: number;
  supplier_invoice_count: number;
  exception_count: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  open_exception_count: number;
  total_financial_impact: string;
  created_at: string;
}

export interface ReconciliationRunDetail extends ReconciliationRunSummary {
  tolerances: Record<string, unknown>;
  input_fingerprint: string;
  exceptions: ReconciliationException[];
}

export interface ReviewCase {
  id: number;
  subject_type: 'document_finding' | 'reconciliation_exception';
  document_finding_id: number | null;
  reconciliation_exception_id: number | null;
  supplier_id: number | null;
  supplier_code?: string | null;
  supplier_name?: string | null;
  subject_summary?: string | null;
  priority: ReviewPriority;
  risk: RiskLevel;
  confidence: string | null;
  financial_impact: string;
  recommended_action: string | null;
  status: ReviewStatus;
  reviewer: string | null;
  reviewer_verified: boolean;
  opened_at: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewSnapshot {
  id: number;
  provider: string;
  model: string;
  prompt_id: string;
  prompt_version: string;
  confidence: string;
  recommendation: string;
  input_hash: string;
  reference_key: string;
  original_output: Record<string, unknown>;
}

export interface ReviewDecision {
  id: number;
  decision: string;
  reviewer: string;
  reason: string | null;
  comment: string | null;
  accepted_recommendation_ref: string | null;
  correction: Record<string, unknown> | null;
  created_at: string;
}

export interface ReviewSubject {
  type: ReviewCase['subject_type'];
  finding: DocumentFinding | null;
  document: { id: number; filename: string; status: string } | null;
  exception: ReconciliationException | null;
}

export interface ReviewDetail extends ReviewCase {
  subject: ReviewSubject;
  snapshot: ReviewSnapshot | null;
  decision: ReviewDecision | null;
}

export interface AuditEvent {
  id: number;
  review_case_id?: number;
  event_type: string;
  actor: string;
  from_status: string | null;
  to_status: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface ReviewMetrics {
  open_cases: number;
  decided_cases: number;
  approved_cases: number;
  rejected_cases: number;
  corrected_cases: number;
  cancelled_cases: number;
  acceptance_rate: number;
  rejection_rate: number;
  correction_rate: number;
  average_review_duration_seconds: number | null;
  in_review?: number;
}

export interface FeedbackRow {
  review_case_id: number;
  input_reference: string;
  input_hash: string | null;
  subject_type: string;
  ai_result: Record<string, unknown> | null;
  confidence: string | null;
  decision: string;
  correction: Record<string, unknown> | null;
  prompt_id: string | null;
  prompt_version: string | null;
  provider: string | null;
  model: string | null;
}

export interface Overview {
  generated_at: string;
  environment: string;
  forecasts: {
    run_count: number;
    latest: ForecastRunSummary | null;
  };
  documents: {
    total: number;
    awaiting_review: number;
    parse_failed: number;
  };
  reconciliation: {
    run_count: number;
    open_exceptions: number;
    error_exceptions: number;
    total_financial_impact: string;
  };
  reviews: ReviewMetrics;
}

export interface SearchResults {
  query: string;
  documents: Array<{
    id: number;
    filename: string;
    supplier_code: string | null;
    status: string;
  }>;
  reviews: Array<{
    id: number;
    status: string;
    subject_type: string;
    priority: string;
  }>;
  exceptions: Array<{
    id: number;
    code: string;
    severity: string;
    reconciliation_run_id: number;
  }>;
  forecasts: Array<{ id: number; model_id: string; cutoff: string }>;
}

export type ForecastPage = Page<ForecastRunSummary>;
export type DocumentPage = Page<DocumentSummary>;
export type ReconciliationPage = Page<ReconciliationRunSummary>;
export type ExceptionPage = Page<ReconciliationException>;
export type ReviewPage = Page<ReviewCase>;
export type AuditPage = Page<AuditEvent>;

export type JobKind = 'document_intake' | 'reconciliation' | 'forecast';

export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface Job {
  id: number;
  kind: JobKind;
  state: JobState;
  requested_by: string;
  requested_by_verified: boolean;
  request: Record<string, unknown>;
  result: Record<string, unknown> | null;
  failure_reason: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
