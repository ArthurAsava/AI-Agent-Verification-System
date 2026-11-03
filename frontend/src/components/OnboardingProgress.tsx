
interface Props {
  percentage: number;
  completedFields: number;
  totalFields: number;
}

export default function OnboardingProgress({
  percentage,
  completedFields,
  totalFields,
}: Props) {
  return (
    <section
      style={{
        padding: "20px",
        border: "1px solid #ddd",
        borderRadius: "12px",
        marginBottom: "24px",
      }}
    >
      <h2>Profile completion</h2>

      <p>
        {completedFields} of {totalFields}
        {" "}required fields completed
      </p>

      <div
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Profile completion"
        style={{
          height: "14px",
          background: "#e5e7eb",
          borderRadius: "8px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${percentage}%`,
            background: "#16a34a",
            transition: "width 0.3s",
          }}
        />
      </div>

      <p>{percentage}% complete</p>
    </section>
  );
}
