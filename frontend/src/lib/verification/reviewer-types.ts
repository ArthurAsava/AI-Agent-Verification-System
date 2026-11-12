
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
