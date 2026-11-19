"use client";

import { useEffect, useRef, useState } from "react";

import {
  KycApiError,
  startDiditSession,
  uploadBiometricSelfie,
} from "@/lib/kyc-api";

function errorMessage(error: unknown): string {
  if (error instanceof KycApiError && error.status === 401) {
    return "Please sign in again before capturing your selfie.";
  }

  return error instanceof Error
    ? error.message
    : "Unable to save your biometric selfie.";
}

type BiometricSelfieCaptureProps = {
  diditOnly?: boolean;
};

export default function BiometricSelfieCapture({
  diditOnly = false,
}: BiometricSelfieCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [consent, setConsent] = useState(false);
  const [diditConsent, setDiditConsent] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [startingDidit, setStartingDidit] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
  }

  useEffect(() => stopCamera, []);

  async function startCamera() {
    if (!consent || capturing || startingDidit) return;

    setError("");
    setMessage("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser does not support camera capture.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });

      streamRef.current = stream;

      if (!videoRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error("Camera preview is unavailable.");
      }

      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraActive(true);
    } catch {
      stopCamera();
      setError(
        "Camera access was not available. Check your browser permission and try again."
      );
    }
  }

  async function captureSelfie() {
    const video = videoRef.current;

    if (!video || !cameraActive || capturing) return;

    const width = video.videoWidth;
    const height = video.videoHeight;

    if (Math.min(width, height) < 320) {
      setError("Use a clear camera image at least 320 pixels wide and high.");
      return;
    }

    setCapturing(true);
    setError("");
    setMessage("");

    try {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;

      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error("Camera image processing is unavailable.");
      }

      context.drawImage(video, 0, 0, width, height);

      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (value) => {
            if (value) resolve(value);
            else reject(new Error("Could not capture the camera image."));
          },
          "image/jpeg",
          0.9
        );
      });

      const selfie = new File(
        [blob],
        "biometric-selfie.jpg",
        { type: "image/jpeg" }
      );

      await uploadBiometricSelfie(selfie);
      stopCamera();

      setMessage(
        "Selfie captured securely. It is available to the biometric review workflow; this does not grant automatic approval."
      );
    } catch (captureError) {
      setError(errorMessage(captureError));
    } finally {
      setCapturing(false);
    }
  }

  async function beginDiditVerification() {
    if (!diditConsent || capturing || startingDidit) return;

    setStartingDidit(true);
    setError("");
    setMessage("");
    stopCamera();

    try {
      const session = await startDiditSession();
      window.location.assign(session.verification_url);
    } catch (diditError) {
      setError(errorMessage(diditError));
      setStartingDidit(false);
    }
  }

  return (
    <section style={{ marginTop: 32 }} aria-labelledby="biometric-heading">
      <h3 id="biometric-heading">Biometric selfie</h3>
      <p>
        {diditOnly
          ? "Didit will collect the required face-match and liveness evidence in its hosted sandbox. This does not grant automatic approval."
          : "Capture a current selfie for a human review, or use Didit’s hosted verification flow for provider-managed document, selfie, and liveness checks. Neither path automatically approves an account."}
      </p>

      {!diditOnly && (
        <label style={{ display: "block", marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={consent}
            disabled={cameraActive || capturing}
            onChange={(event) => setConsent(event.target.checked)}
          />{" "}
          I consent to Verity storing this selfie solely for identity
          verification and human review.
        </label>
      )}

      <label style={{ display: "block", marginBottom: 12 }}>
        <input
          type="checkbox"
          checked={diditConsent}
          disabled={cameraActive || capturing || startingDidit}
          onChange={(event) => setDiditConsent(event.target.checked)}
        />{" "}
        I consent to Didit processing my identity document, selfie, and
        liveness data in its hosted verification flow. This is optional and
        does not grant automatic approval.
      </label>

      <button
        type="button"
        disabled={!diditConsent || cameraActive || capturing || startingDidit}
        onClick={() => void beginDiditVerification()}
      >
        {startingDidit ? "Opening Didit..." : "Start Didit verification"}
      </button>

      {!diditOnly && !cameraActive ? (
        <button
          type="button"
          disabled={!consent || capturing || startingDidit}
          onClick={() => void startCamera()}
        >
          Open camera
        </button>
      ) : !diditOnly ? (
        <>
          <video
            ref={videoRef}
            muted
            playsInline
            aria-label="Live camera preview"
            style={{
              display: "block",
              width: "100%",
              maxWidth: 480,
              marginTop: 12,
              borderRadius: 8,
              background: "#111827",
            }}
          />
          <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
            <button
              type="button"
              disabled={capturing}
              onClick={() => void captureSelfie()}
            >
              {capturing ? "Saving selfie..." : "Capture selfie"}
            </button>
            <button
              type="button"
              disabled={capturing}
              onClick={stopCamera}
            >
              Cancel
            </button>
          </div>
        </>
      ) : null}

      {error && <p role="alert" style={{ color: "#b91c1c" }}>{error}</p>}
      {message && <p role="status" style={{ color: "#166534" }}>{message}</p>}
    </section>
  );
}
