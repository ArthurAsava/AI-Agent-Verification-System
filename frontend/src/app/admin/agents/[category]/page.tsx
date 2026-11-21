import { Suspense } from "react";

import AppHeader from "@/components/AppHeader";

import AgentCategoryClient from "./AgentCategoryClient";

type PageProps = {
  params: Promise<{ category: string }>;
};

async function AgentCategoryContent({ params }: PageProps) {
  const { category } = await params;
  return <AgentCategoryClient category={category} />;
}

export default function AgentCategoryPage({ params }: PageProps) {
  return (
    <Suspense
      fallback={
        <main className="app-page">
          <AppHeader />
          <div className="app-content">
            <p>Loading agent directory...</p>
          </div>
        </main>
      }
    >
      <AgentCategoryContent params={params} />
    </Suspense>
  );
}
