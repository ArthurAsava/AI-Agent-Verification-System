"use client";

import Link from "next/link";
import useSWR from "swr";

import AppHeader from "@/components/AppHeader";
import { getAdminAgents } from "@/lib/verification/reviewer-api";
import type {
  AdminAgentCategory,
  AdminAgentRecord,
} from "@/lib/verification/reviewer-types";

const CATEGORY_DETAILS: Record<
  AdminAgentCategory,
  { title: string; description: string }
> = {
  waiting: {
    title: "Agents waiting for review",
    description:
      "Profiles that are still in onboarding or awaiting a staff verification decision.",
  },
  approved: {
    title: "Approved & active agents",
    description:
      "Agents whose profiles have been approved by a Verity administrator or reviewer.",
  },
  rejected: {
    title: "Rejected agents",
    description:
      "Agents whose current verification submission was rejected.",
  },
};

function isAgentCategory(value: string): value is AdminAgentCategory {
  return value === "waiting" || value === "approved" || value === "rejected";
}

function formatDate(value: string | null) {
  if (!value) return "Not provided";

  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusLabel(status: AdminAgentRecord["status"]) {
  switch (status) {
    case "under_review":
      return "Awaiting review";
    case "approved":
      return "Approved";
    case "rejected":
      return "Rejected";
    case "pending":
      return "Onboarding in progress";
    case "suspended":
      return "Suspended";
  }
}

export default function AgentCategoryClient({ category }: { category: string }) {
  const validCategory = isAgentCategory(category) ? category : null;
  const details = validCategory ? CATEGORY_DETAILS[validCategory] : null;
  const query = useSWR(
    validCategory ? ["admin-agent-category", validCategory] : null,
    ([, currentCategory]: [string, AdminAgentCategory]) =>
      getAdminAgents(currentCategory),
    { revalidateOnFocus: false },
  );

  const errorMessage =
    query.error instanceof Error
      ? query.error.message
      : query.error
        ? "Unable to load these agents."
        : null;

  if (!validCategory || !details) {
    return (
      <main className="app-page">
        <AppHeader />
        <div className="app-content workspace-stack">
          <section className="app-panel">
            <h1 className="app-title">Agent category not found.</h1>
            <Link className="button button--dark" href="/admin">
              Return to admin dashboard
            </Link>
          </section>
        </div>
      </main>
    );
  }

  const agents = query.data?.agents ?? [];

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content workspace-stack">
        <header className="workspace-heading">
          <div>
            <p className="app-eyebrow">Administrator directory</p>
            <h1 className="app-title">{details.title}</h1>
            <p className="app-subtitle">{details.description}</p>
          </div>
          <div className="flex gap-3">
            {category === "waiting" && (
              <Link className="button button--gold" href="/reviewer">
                Open review queue
              </Link>
            )}
            <Link className="button button--dark" href="/admin">
              Back to admin dashboard
            </Link>
          </div>
        </header>

        {query.isLoading && <p role="status">Loading agent records...</p>}

        {errorMessage && (
          <section className="app-panel" role="alert">
            <h2>Could not load agents.</h2>
            <p>{errorMessage}</p>
          </section>
        )}

        {!query.isLoading && !errorMessage && agents.length === 0 && (
          <section className="app-panel">
            <h2>No agents in this category.</h2>
            <p>Agent records will appear here as their verification status changes.</p>
          </section>
        )}

        {!query.isLoading && !errorMessage && agents.length > 0 && (
          <section className="workspace-stack" aria-label={details.title}>
            {agents.map((agent) => (
              <article className="app-panel" key={agent.id}>
                <div className="profile-summary__heading">
                  <div>
                    <p className="app-eyebrow">{statusLabel(agent.status)}</p>
                    <h2>
                      {agent.first_name} {agent.last_name}
                    </h2>
                  </div>
                  <p className="status-message">Updated {formatDateTime(agent.updated_at)}</p>
                </div>

                <dl className="profile-details-grid">
                  <div><dt>Date of birth</dt><dd>{formatDate(agent.date_of_birth)}</dd></div>
                  <div><dt>Sex</dt><dd>{agent.avatar_variant ? agent.avatar_variant[0].toUpperCase() + agent.avatar_variant.slice(1) : "Not provided"}</dd></div>
                  <div><dt>Primary residence</dt><dd>{agent.primary_residence ?? "Not provided"}</dd></div>
                  <div><dt>Nationality</dt><dd>{agent.nationality ?? "Not provided"}</dd></div>
                  <div><dt>Phone</dt><dd>{agent.phone_number ?? "Not provided"}</dd></div>
                  <div><dt>Profile reference</dt><dd>{agent.id}</dd></div>
                </dl>
              </article>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
