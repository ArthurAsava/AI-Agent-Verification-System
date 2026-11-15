
import {
  STATUS_INFORMATION,
  type VerificationCaseStatus,
} from "@/lib/verification/types";

interface Props {
  status: VerificationCaseStatus;
}

const COLORS = {
  gray: "bg-gray-100 text-gray-700",
  blue: "bg-blue-100 text-blue-700",
  amber: "bg-amber-100 text-amber-800",
  green: "bg-green-100 text-green-800",
  red: "bg-red-100 text-red-700",
};

export default function VerificationStatusBadge({
  status,
}: Props) {
  const information = STATUS_INFORMATION[status];

  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
        COLORS[information.color]
      }`}
    >
      {information.label}
    </span>
  );
}
