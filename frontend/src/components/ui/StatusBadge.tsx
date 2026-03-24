import type { GoalStatus } from "../../types";

interface StatusBadgeProps {
  status: GoalStatus;
}

const STATUS_CONFIG: Record<
  GoalStatus,
  { label: string; className: string }
> = {
  active: {
    label: "ACTIVE",
    className: "bg-secondary-container text-black border-black",
  },
  done: {
    label: "DONE",
    className: "bg-[#2ECC40] text-white border-black",
  },
  blocked: {
    label: "BLOCKED",
    className: "bg-tertiary text-white border-black",
  },
  clarifying: {
    label: "CLARIFYING",
    className: "bg-primary-container text-white border-black",
  },
  planning: {
    label: "PLANNING",
    className: "bg-cyan-400 text-black border-black",
  },
  drafting: {
    label: "DRAFTING",
    className: "bg-gray-400 text-white border-black",
  },
  archived: {
    label: "ARCHIVED",
    className: "bg-gray-200 text-gray-600 border-black",
  },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const { label, className } = STATUS_CONFIG[status] ?? STATUS_CONFIG.drafting;
  return (
    <span
      className={`border-2 rounded-full px-3 py-0.5 font-headline font-bold text-[10px] uppercase ${className}`}
    >
      {label}
    </span>
  );
}
