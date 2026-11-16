
import { Suspense } from "react";

import AppHeader from "@/components/AppHeader";

import ReviewerCaseClient from "./ReviewerCaseClient";

interface Props {
  params: Promise<{
    caseId: string;
  }>;
}

async function ReviewerCaseContent({
  params,
}: Props) {
  const { caseId } = await params;

  return <ReviewerCaseClient caseId={caseId} />;
}

export default function ReviewerCasePage({
  params,
}: Props) {
  return (
    <Suspense
      fallback={
        <main className="app-page">
          <AppHeader />
          <div className="app-content">
            <p className="text-slate-600">
              Loading verification case...
            </p>
          </div>
        </main>
      }
    >
      <ReviewerCaseContent params={params} />
    </Suspense>
  );
}
