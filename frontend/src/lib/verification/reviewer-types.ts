
import type { VerificationCase } from "./types";

export type ReviewerAction =
  | "approve"
  | "reject"
  | "request_resubmission";

export interface ReviewerCase extends VerificationCase {
  recommendation: string | null;
  risk_score: number | null;
  risk_level: string | null;
  scoring_version: string | null;
  reviewer_user_id: string | null;
  decision_reason: string | null;
  reviewed_at: string | null;
}

export interface ReviewQueueResponse {
  cases: ReviewerCase[];
}

export interface VerificationDecisionRequest {
  action: ReviewerAction;
  reason: string;
  expected_version: number;
}

export interface VerificationDecisionResponse {
  case_id: string;
  previous_status: string;
  new_status: string;
  version: number;
  reviewed_at: string;
}

export interface ReviewerDocumentSummary {
  document_id: string;
  document_type: string;
  original_filename: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  status: string;
}

export interface BiometricProviderSummary {
  provider: string;
  mode: string;
  submission_status: string;
  result_code: string | null;
  result_text: string | null;
  is_final: boolean | null;
  actions: Record<string, string>;
}

export interface BiometricReviewItem {
  check_id: string;
  agent_id: string;
  created_at: string | null;
  selfie: ReviewerDocumentSummary | null;
  identity_documents: ReviewerDocumentSummary[];
  provider_summary: BiometricProviderSummary | null;
}

export interface BiometricReviewQueueResponse {
  items: BiometricReviewItem[];
}

export type BiometricReviewerAction =
  | "confirm_match"
  | "request_resubmission"
  | "reject_capture";

export interface BiometricReviewDecisionRequest {
  action: BiometricReviewerAction;
  reason: string;
}

export interface BiometricReviewDecisionResponse {
  check_id: string;
  previous_status: string;
  new_status: string;
  reviewed_at: string;
}
