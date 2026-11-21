
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
  fraud_assessment: ReviewerFraudAssessment | null;
}

export interface FraudSignal {
  code: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  evidence: Record<string, string | number | boolean>;
}

export interface ReviewerFraudAssessment {
  id: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  model_version: string;
  requires_review: boolean;
  signals: FraudSignal[];
  created_at: string;
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

export interface AdminDashboardSummary {
  awaiting_review_cases: number;
  elevated_risk_cases: number;
  new_cases_last_24_hours: number;
  agents_under_review: number;
  active_reviewers: number;
  waiting_agents: number;
  approved_agents: number;
  rejected_agents: number;
}

export type AdminAgentCategory =
  | "waiting"
  | "approved"
  | "rejected";

export interface AdminAgentRecord {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  phone_number: string | null;
  date_of_birth: string | null;
  primary_residence: string | null;
  nationality: string | null;
  avatar_variant: "male" | "female" | null;
  status: "pending" | "under_review" | "approved" | "rejected" | "suspended";
  created_at: string;
  updated_at: string;
}

export interface AdminAgentListResponse {
  category: AdminAgentCategory;
  agents: AdminAgentRecord[];
}

export interface ReviewerAccessEntry {
  user_id: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface ReviewerAccessListResponse {
  reviewers: ReviewerAccessEntry[];
}

export interface ReviewerAccessUpdateRequest {
  is_active: boolean;
  is_admin: boolean;
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
