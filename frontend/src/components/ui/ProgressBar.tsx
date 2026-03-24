import type { GoalStatus } from "../../types";

interface ProgressBarProps {
  completed: number;
  total: number;
  status?: GoalStatus;
}

const STATUS_BAR_COLOR: Record<string, string> = {
  active: "bg-primary-container",
  done: "bg-[#2ECC40]",
  blocked: "bg-tertiary",
  clarifying: "bg-primary-container/20",
  planning: "bg-cyan-400",
  drafting: "bg-gray-300",
  archived: "bg-gray-300",
};

export default function ProgressBar({ completed, total, status = "active" }: ProgressBarProps) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const barColor = STATUS_BAR_COLOR[status] ?? "bg-primary-container";

  return (
    <div className="h-6 border-2 border-black bg-surface p-1">
      <div
        className={`h-full ${barColor} ${status === "active" ? "border-r-2 border-black" : ""} transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
