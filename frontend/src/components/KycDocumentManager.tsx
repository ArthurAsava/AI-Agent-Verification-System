
"use client";

import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import {
  KycApiError,
  listKycDocuments,
  uploadKycDocument,
  downloadKycDocument,
  submitKycDocumentForVerification,
  type KycDocument,
} from "@/lib/kyc-api";

const MAX_SIZE = 5 * 1024 * 1024;

const DOCUMENT_TYPES = [
  { value: "national_id_front", label: "National ID — Front" },
  { value: "national_id_back", label: "National ID — Back" },
  { value: "passport", label: "Passport" },
  { value: "proof_of_address", label: "Proof of Address" },
];

// Must match the document types accepted by FastAPI.
// These are the types used in the Phase 7B upload service.

function displayStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatBytes(bytes: number) {
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function canSubmitForVerification(document: KycDocument) {
  return ["national_id_front", "passport"].includes(
    document.document_type
  );
}

function errorMessage(error: unknown) {
  if (error instanceof KycApiError && error.status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  return error instanceof Error
    ? error.message
    : "An unexpected error occurred.";
}

export default function KycDocumentManager() {
  const [documents, setDocuments] = useState<KycDocument[]>([]);
  const [documentType, setDocumentType] = useState(
    "national_id_front"
  );
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(
    null
  );
  const [verifyingId, setVerifyingId] = useState<string | null>(
    null
  );
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadDocuments = useCallback(async () => {
    const result = await listKycDocuments();
    setDocuments(result);
  }, []);

  useEffect(() => {
    let active = true;

    listKycDocuments()
      .then((result) => {
        if (active) setDocuments(result);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setError("");
    setMessage("");

    const selected = event.target.files?.[0] ?? null;
    setFile(null);

    if (!selected) return;

    if (selected.size === 0 || selected.size > MAX_SIZE) {
      setError("Choose a non-empty file smaller than 5 MiB.");
      event.target.value = "";
      return;
    }

    const extension = selected.name.split(".").pop()?.toLowerCase();

    if (!extension || !["pdf", "png", "jpg", "jpeg"].includes(extension)) {
      setError("Only PDF, PNG and JPEG files are supported.");
      event.target.value = "";
      return;
    }

    setFile(selected);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!file || uploading) return;

    setUploading(true);
    setError("");
    setMessage("");

    try {
      const uploaded = await uploadKycDocument(documentType, file);
      await loadDocuments();

      setFile(null);

      if (canSubmitForVerification(uploaded)) {
        await handleVerification(uploaded);
      } else {
        setMessage(
          "Document uploaded. Upload a National ID front or passport to start identity verification."
        );
      }

      const input = document.getElementById(
        "kyc-document-file"
      ) as HTMLInputElement | null;

      if (input) input.value = "";
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleVerification(document: KycDocument) {
    if (verifyingId) return;

    setVerifyingId(document.document_id);
    setError("");

    try {
      const result = await submitKycDocumentForVerification(
        document.document_id
      );

      setMessage(result.message);
      await loadDocuments();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setVerifyingId(null);
    }
  }

  async function handleDownload(document: KycDocument) {
    setDownloadingId(document.document_id);
    setError("");

    try {
      const blob = await downloadKycDocument(
        document.document_id
      );

      const url = URL.createObjectURL(blob);

      const link = window.document.createElement("a");
      link.href = url;
      link.download =
        document.original_filename || "kyc-document";
      window.document.body.appendChild(link);
      link.click();
      link.remove();

      window.setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <h3>Upload identity documents</h3>

      <p>
        Accepted formats: PDF, PNG and JPEG.
        Maximum file size: 5 MiB.
      </p>

      <form onSubmit={handleUpload}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="kyc-document-type">
            Document type
          </label>

          <select
            id="kyc-document-type"
            value={documentType}
            onChange={(event) =>
              setDocumentType(event.target.value)
            }
            disabled={uploading}
            style={{ display: "block", padding: 8 }}
          >
            {DOCUMENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label htmlFor="kyc-document-file">
            Choose document
          </label>

          <input
            id="kyc-document-file"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={handleFileChange}
            disabled={uploading}
            style={{ display: "block", marginTop: 8 }}
          />
        </div>

        <button
          type="submit"
          disabled={!file || uploading}
        >
          {uploading ? "Uploading..." : "Upload document"}
        </button>
      </form>

      {error && (
        <p role="alert" style={{ color: "#b91c1c" }}>
          {error}
        </p>
      )}

      {message && (
        <p role="status" style={{ color: "#166534" }}>
          {message}
        </p>
      )}

      <h3 style={{ marginTop: 32 }}>My uploaded documents</h3>

      {loading ? (
        <p>Loading documents...</p>
      ) : documents.length === 0 ? (
        <p>No documents uploaded yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {documents.map((doc) => (
            <li
              key={doc.document_id}
              style={{
                border: "1px solid #d1d5db",
                borderRadius: 8,
                padding: 16,
                marginBottom: 12,
                overflowWrap: "anywhere",
              }}
            >
              <strong>{doc.original_filename}</strong>

              <p>
                {DOCUMENT_TYPES.find(
                  (type) => type.value === doc.document_type
                )?.label ?? doc.document_type}
              </p>

              <p>Size: {formatBytes(doc.file_size_bytes)}</p>
              <p>Status: {displayStatus(doc.status)}</p>

              <button
                type="button"
                disabled={
                  downloadingId !== null || verifyingId !== null
                }
                onClick={() => void handleDownload(doc)}
              >
                {downloadingId === doc.document_id
                  ? "Downloading..."
                  : "Download"}
              </button>

              {canSubmitForVerification(doc) && (
                <button
                  type="button"
                  disabled={
                    downloadingId !== null || verifyingId !== null
                  }
                  onClick={() => void handleVerification(doc)}
                  style={{ marginLeft: 12 }}
                >
                  {verifyingId === doc.document_id
                    ? "Submitting..."
                    : "Start verification"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
