
"use client";
import KycDocumentManager from "@/components/KycDocumentManager";
import BiometricSelfieCapture from "@/components/BiometricSelfieCapture";
import Link from "next/link";

import { useEffect, useState } from "react";

import {
  getKycRequirements,
  type KycRequirements,
} from "@/lib/agent-api";


export default function KycChecklist() {
  const [requirements, setRequirements] =
    useState<KycRequirements | null>(null);

  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getKycRequirements()
      .then((result) => {
        if (active) setRequirements(result);
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load requirements"
          );
        }
      });

    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (!requirements) {
    return <p>Loading KYC requirements...</p>;
  }

  return (
    <section>
      <h3>Accepted identity documents</h3>

      <p>
        Prepare one of the following documents:
      </p>

      <ul>
        {requirements.identity_documents.options.map(
          (document) => (
            <li key={document.code}>
              <strong>{document.name}</strong>
              <p>{document.description}</p>
            </li>
          )
        )}
      </ul>

      <h3>Preparation guidelines</h3>

      <ul>
        {requirements.guidelines.map(
          (guideline) => (
            <li key={guideline}>{guideline}</li>
          )
        )}
      </ul>

      {!requirements.uploads_enabled && (
        <p>
          Secure document uploads are not yet
          available. Do not submit identity
          documents at this stage.
        </p>
      )}
      <KycDocumentManager />
      <BiometricSelfieCapture />
      <Link className="button button--gold" href="/dashboard/verification">
        Track verification status <span aria-hidden="true">→</span>
      </Link>
    </section>
  );
}
