
import { Suspense } from "react";

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
        <main className="min-h-screen bg-slate-50 px-6 py-10">
          <div className="mx-auto max-w-4xl">
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
