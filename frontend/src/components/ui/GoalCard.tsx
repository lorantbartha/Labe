import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { goalsApi } from "../../api/goals";
import type { Goal } from "../../types";
import ProgressBar from "./ProgressBar";
import StatusBadge from "./StatusBadge";

interface GoalCardProps {
  goal: Goal;
}

function formatDueDate(dueDate: string | null): string {
  if (!dueDate) return "";
  const due = new Date(dueDate);
  const now = new Date();
  const diffMs = due.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `Overdue by ${Math.abs(diffDays)} days`;
  if (diffDays === 0) return "Due today";
  if (diffDays < 7) return `Due in ${diffDays} days`;
  const diffMonths = Math.round(diffDays / 30);
  if (diffMonths < 1) return `Due in ${diffDays} days`;
  return `Due in ${diffMonths} month${diffMonths !== 1 ? "s" : ""}`;
}

const CARD_HEADER_BG: Record<string, string> = {
  active: "bg-primary-container/10",
  done: "bg-gray-100",
  blocked: "bg-tertiary/10",
  clarifying: "bg-primary-container/20",
  planning: "bg-cyan-100",
  drafting: "bg-gray-100",
  archived: "bg-gray-100",
};

const CARD_FOOTER: Record<
  string,
  { shell: string; action: string; text: string; label: string; icon: string }
> = {
  active: {
    shell: "bg-stone-50",
    action: "bg-secondary-container",
    text: "text-black",
    label: "Open Plan",
    icon: "chevron_right",
  },
  done: {
    shell: "bg-stone-50",
    action: "bg-green-100",
    text: "text-black",
    label: "Archive Goal",
    icon: "archive",
  },
  blocked: {
    shell: "bg-stone-50",
    action: "bg-orange-100",
    text: "text-black",
    label: "Open Plan",
    icon: "bolt",
  },
  clarifying: {
    shell: "bg-stone-50",
    action: "bg-primary-container/15",
    text: "text-black",
    label: "Answer Questions",
    icon: "edit_note",
  },
  planning: {
    shell: "bg-stone-50",
    action: "bg-cyan-100",
    text: "text-black",
    label: "Open Plan",
    icon: "reorder",
  },
  drafting: {
    shell: "bg-stone-50",
    action: "bg-gray-100",
    text: "text-black",
    label: "Complete Draft",
    icon: "edit",
  },
  archived: {
    shell: "bg-stone-50",
    action: "bg-gray-100",
    text: "text-black",
    label: "View Goal",
    icon: "visibility",
  },
};

const STATUS_META: Record<string, { icon: string; className: string; label: (g: Goal) => string }> = {
  active: {
    icon: "schedule",
    className: "text-tertiary",
    label: (g) => (g.due_date ? formatDueDate(g.due_date) : "In progress"),
  },
  done: {
    icon: "check_circle",
    className: "text-on-surface-variant",
    label: () => "Completed",
  },
  blocked: {
    icon: "error",
    className: "text-tertiary",
    label: (g) => `Friction: ${g.blocker_reason ?? "Unknown"}`,
  },
  clarifying: {
    icon: "map",
    className: "text-on-surface-variant",
    label: () => "Discovery Phase",
  },
  planning: {
    icon: "calendar_today",
    className: "text-on-surface-variant",
    label: (g) => (g.due_date ? `Starts ${new Date(g.due_date).toLocaleDateString("en-US", { month: "short", year: "numeric" })}` : "In planning"),
  },
  drafting: {
    icon: "edit",
    className: "text-on-surface-variant",
    label: () => "Incomplete Definition",
  },
  archived: {
    icon: "archive",
    className: "text-on-surface-variant",
    label: () => "Archived",
  },
};

export default function GoalCard({ goal }: GoalCardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const headerBg = CARD_HEADER_BG[goal.status] ?? "bg-gray-100";
  const footer = CARD_FOOTER[goal.status] ?? CARD_FOOTER.drafting;
  const meta = STATUS_META[goal.status] ?? STATUS_META.drafting;

  const { mutate: archive } = useMutation({
    mutationFn: () => goalsApi.archiveGoal(goal.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });

  function handleCardClick() {
    if (goal.status === "clarifying") {
      navigate(`/goals/${goal.id}/clarify`);
    } else if (["active", "planning", "blocked", "done"].includes(goal.status)) {
      navigate(`/goals/${goal.id}/plan`);
    }
  }

  function handleFooterClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (goal.status === "done") {
      archive();
    } else {
      handleCardClick();
    }
  }

  return (
    <div
      className="bg-white border-4 border-black shadow-neobrutal flex flex-col group hover:-translate-y-1 transition-all cursor-pointer"
      onClick={handleCardClick}
    >
      {/* Header */}
      <div className={`p-4 border-b-2 border-black flex justify-between items-center ${headerBg}`}>
        <StatusBadge status={goal.status} />
        <span className="font-headline font-bold text-[10px] uppercase opacity-50">
          GOAL_ID: {goal.id.toUpperCase()}
        </span>
      </div>

      {/* Body */}
      <div className="p-5 flex-grow">
        <h3
          className={[
            "font-headline font-black text-2xl uppercase leading-tight mb-4",
            goal.status === "drafting" ? "opacity-60 italic" : "",
            goal.status === "clarifying" ? "text-primary" : "",
          ].join(" ")}
        >
          {goal.title}
        </h3>

        <div className="space-y-4">
          <div className="flex justify-between items-end mb-1">
            <span className="font-headline font-bold text-[10px] uppercase">Execution Logic</span>
            <span className="font-headline font-bold text-xs">
              {goal.milestones_completed}/{goal.milestones_total} MILESTONES
            </span>
          </div>
          <ProgressBar
            completed={goal.milestones_completed}
            total={goal.milestones_total}
            status={goal.status}
          />
          <div className={`flex items-center gap-2 ${meta.className}`}>
            <span className="material-symbols-outlined text-sm">{meta.icon}</span>
            <span className="font-headline font-bold text-[10px] uppercase">{meta.label(goal)}</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        className={`p-3 border-t-2 border-black ${footer.shell}`}
        onClick={handleFooterClick}
      >
        <div
          className={`border-2 border-black px-4 py-3 flex justify-between items-center shadow-neobrutal transition-transform group-hover:-translate-y-0.5 ${footer.action} ${footer.text}`}
        >
          <span className="font-headline font-bold text-[10px] uppercase tracking-widest">
            {footer.label}
          </span>
          <span className="material-symbols-outlined">{footer.icon}</span>
        </div>
      </div>
    </div>
  );
}
