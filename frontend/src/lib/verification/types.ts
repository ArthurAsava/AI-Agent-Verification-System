
export type VerificationCaseStatus =
  | "pending"
  | "analyzing"
  | "awaiting_review"
  | "approved"
  | "rejected"
  | "resubmission_required"
  | "analysis_failed";

export interface VerificationCase {
  id: string;
  agent_id: string;
  document_id: string;
  status: VerificationCaseStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AgentVerificationResponse {
  cases: VerificationCase[];
}

export interface VerificationStatusInfo {
  label: string;
  description: string;
  color: "gray" | "blue" | "amber" | "green" | "red";
}

export const STATUS_INFORMATION: Record<
  VerificationCaseStatus,
  VerificationStatusInfo
> = {
  pending: {
    label: "Pending",
    description: "Your verification request is waiting to be processed.",
    color: "gray",
  },
  analyzing: {
    label: "Analyzing",
    description: "Your submitted document is being analyzed.",
    color: "blue",
  },
  awaiting_review: {
    label: "Awaiting Review",
    description: "Your verification results are awaiting a human review.",
    color: "amber",
  },
  approved: {
    label: "Approved",
    description: "Your verification has been approved.",
    color: "green",
  },
  rejected: {
    label: "Rejected",
    description: "Your verification application was rejected.",
    color: "red",
  },
  resubmission_required: {
    label: "Resubmission Required",
    description: "You need to submit updated verification documents.",
    color: "amber",
  },
  analysis_failed: {
    label: "Analysis Failed",
    description: "The verification analysis could not be completed.",
    color: "red",
  },
};
