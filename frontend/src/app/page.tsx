
import BackendStatus from "@/components/BackendStatus";

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "2rem",
        textAlign: "center",
        gap: "1rem",
      }}
    >
      <h1>AI Agent Verification System</h1>

      <p>
        Secure agent registration and identity verification
        for the SalesMesh platform.
      </p>

      <BackendStatus />

      <p>Version 0.1.0</p>
    </main>
  );
}
