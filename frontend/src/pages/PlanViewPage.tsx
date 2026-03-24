import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { goalsApi } from "../api/goals";
import TopNavBar from "../components/layout/TopNavBar";
import type { Goal, Milestone, MilestoneStatus, Step } from "../types";
import { computeDagLayout, type Position } from "../utils/dagLayout";

const MILESTONE_STYLES: Record<MilestoneStatus, { card: string; text: string; icon: string }> = {
  done: { card: "bg-green-500 border-4 border-black", text: "text-black", icon: "check_circle" },
  active: { card: "bg-secondary-container border-4 border-black ring-4 ring-black ring-offset-2", text: "text-black", icon: "radio_button_checked" },
  blocked: { card: "bg-error-container border-4 border-black", text: "text-on-error", icon: "block" },
  pending: { card: "bg-white border-4 border-black border-dashed", text: "text-gray-400", icon: "star" },
};

interface NodeCardProps {
  milestone: Milestone;
  position: Position;
  isSelected: boolean;
  onClick: () => void;
}

function NodeCard({ milestone, position, isSelected, onClick }: NodeCardProps) {
  const style = MILESTONE_STYLES[milestone.status];
  const pct = milestone.steps_total > 0
    ? Math.round((milestone.steps_completed / milestone.steps_total) * 100)
    : 0;

  return (
    <div
      className={`absolute cursor-pointer group transition-transform hover:-translate-y-1 ${isSelected ? "ring-4 ring-offset-2 ring-black" : ""}`}
      style={{ left: position.x, top: position.y, width: 192, zIndex: 10 }}
      onClick={onClick}
    >
      <div className={`${style.card} p-4 shadow-neobrutal`}>
        <div className="flex justify-between mb-2">
          <span className={`font-mono text-[10px] font-bold ${style.text}`}>{milestone.node_id}</span>
          <span className={`material-symbols-outlined text-sm ${milestone.status === "active" ? "animate-pulse" : ""} ${style.text}`}>
            {style.icon}
          </span>
        </div>
        <h3 className={`font-headline font-bold text-xs uppercase leading-tight ${style.text}`}>
          {milestone.title}
        </h3>
        {milestone.description && (
          <p className={`font-mono text-[9px] mt-1 ${style.text} opacity-70 leading-snug normal-case`}>
            {milestone.description}
          </p>
        )}
        {milestone.blocker_reason && (
          <p className={`font-mono text-[9px] mt-2 ${style.text} opacity-70`}>
            BLOCKED BY: {milestone.blocker_reason.toUpperCase()}
          </p>
        )}
        {milestone.status === "active" && (
          <div className="mt-3 h-1 bg-black/20 overflow-hidden">
            <div className="bg-black h-full transition-all" style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}

function MilestoneConnectors({
  milestones,
  positions,
}: {
  milestones: Milestone[];
  positions: Map<string, Position>;
}) {
  const lines: { x1: number; y1: number; x2: number; y2: number; key: string }[] = [];
  for (const m of milestones) {
    const mPos = positions.get(m.id);
    if (!mPos) continue;
    for (const depId of m.depends_on) {
      const depPos = positions.get(depId);
      if (!depPos) continue;
      // Connect center-bottom of dep to center-top of m
      const x1 = depPos.x + 96;
      const y1 = depPos.y + 80; // approx card height
      const x2 = mPos.x + 96;
      const y2 = mPos.y;
      lines.push({ x1, y1, x2, y2, key: `${depId}-${m.id}` });
    }
  }

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="black" />
        </marker>
      </defs>
      {lines.map(({ x1, y1, x2, y2, key }) => (
        <g key={key}>
          <line x1={x1} y1={y1} x2={x1} y2={(y1 + y2) / 2} stroke="black" strokeWidth="2" />
          <line x1={x1} y1={(y1 + y2) / 2} x2={x2} y2={(y1 + y2) / 2} stroke="black" strokeWidth="2" />
          <line
            x1={x2} y1={(y1 + y2) / 2}
            x2={x2} y2={y2 - 4}
            stroke="black" strokeWidth="2"
            markerEnd="url(#arrowhead)"
          />
        </g>
      ))}
    </svg>
  );
}

function TaskItem({ step, goalId, disabled }: { step: Step; goalId: string; disabled: boolean }) {
  const queryClient = useQueryClient();
  const { mutate: toggleStep } = useMutation({
    mutationFn: () => goalsApi.updateStep(goalId, step.id, !step.completed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan", goalId] });
    },
  });

  return (
    <li
      className={`bg-white border-2 border-black p-3 shadow-neobrutal group hover:-translate-y-0.5 transition-transform ${step.completed ? "opacity-50" : ""}`}
    >
      <div className="flex gap-3">
        <button
          onClick={() => toggleStep()}
          disabled={disabled}
          className={`w-5 h-5 border-2 border-black flex-shrink-0 flex items-center justify-center transition-colors ${step.completed ? "bg-green-500" : "bg-white group-hover:bg-secondary-container"} ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
        >
          {step.completed && (
            <span className="material-symbols-outlined text-[10px] font-black">check</span>
          )}
        </button>
        <div className="min-w-0">
          <p className={`font-headline font-bold text-xs uppercase ${step.completed ? "line-through" : ""}`}>
            {step.title}
          </p>
          <div className="flex gap-2 mt-1 flex-wrap">
            {step.priority === "high" && (
              <span className="text-[9px] font-mono bg-tertiary/10 text-tertiary px-1 uppercase border border-tertiary/20">
                HIGH_PRIO
              </span>
            )}
            {step.recurring && (
              <span className="text-[9px] font-mono bg-yellow-100 px-1 border border-yellow-200 uppercase">
                Recurring
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function formatElapsed(createdAt: string): string {
  const created = new Date(createdAt);
  const diffMs = Date.now() - created.getTime();
  if (Number.isNaN(created.getTime()) || diffMs < 0) {
    return "Started recently";
  }
  const totalMinutes = Math.floor(diffMs / 60000);
  const totalHours = Math.floor(diffMs / 3600000);
  const totalDays = Math.floor(diffMs / 86400000);
  if (totalDays > 0) {
    return `${totalDays}d ${totalHours % 24}h elapsed`;
  }
  if (totalHours > 0) {
    return `${totalHours}h ${totalMinutes % 60}m elapsed`;
  }
  return `${Math.max(totalMinutes, 1)}m elapsed`;
}

function SummarySection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="bg-white border-2 border-black p-3 shadow-neobrutal">
      <h3 className="font-headline font-bold text-[10px] uppercase text-gray-500 mb-2">{title}</h3>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2 items-start">
            <span className="mt-1 w-2 h-2 bg-black inline-block flex-shrink-0" />
            <p className="font-mono text-[10px] leading-relaxed">{item}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GoalSummaryPanel({ goal }: { goal: Goal }) {
  return (
    <div className="w-full space-y-4">
      <div className="bg-white border-4 border-black p-5 shadow-neobrutal-lg">
        <p className="font-mono text-[10px] uppercase text-gray-500">Goal Overview</p>
        <h1 className="font-headline font-black text-3xl uppercase tracking-tight mt-2 leading-none">
          {goal.title}
        </h1>
        <p className="font-mono text-[10px] uppercase mt-3 text-gray-500">
          {formatElapsed(goal.created_at)}
        </p>
        <p className="font-mono text-[11px] leading-relaxed mt-4">
          {goal.synopsis || goal.description}
        </p>
      </div>

      <SummarySection title="Time Constraints" items={goal.time_constraints} />
      <SummarySection title="Resources" items={goal.resources} />
      <SummarySection title="Current State" items={goal.current_state} />
      <SummarySection title="Success Criteria" items={goal.success_criteria} />
      <SummarySection title="Risks / Unknowns" items={goal.risks_or_unknowns} />
    </div>
  );
}

export default function PlanViewPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedMilestoneId, setSelectedMilestoneId] = useState<string | null>(null);
  const [blockerText, setBlockerText] = useState("");
  const [showBlockerInput, setShowBlockerInput] = useState(false);

  const { data: goal } = useQuery({
    queryKey: ["goal", id],
    queryFn: () => goalsApi.get(id!),
    enabled: !!id,
  });

  const { data: plan, isLoading } = useQuery({
    queryKey: ["plan", id],
    queryFn: () => goalsApi.getPlan(id!),
    enabled: !!id,
  });

  const { mutate: reportBlocker, isPending: isReporting } = useMutation({
    mutationFn: () => goalsApi.reportBlocker(id!, blockerText),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goal", id] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      setShowBlockerInput(false);
      setBlockerText("");
    },
  });

  const { mutate: completeMilestone, isPending: isCompletingMilestone } = useMutation({
    mutationFn: () => goalsApi.updateMilestone(id!, selectedMilestoneId!, "done"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
      queryClient.invalidateQueries({ queryKey: ["goal", id] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
    },
  });

  const positions = computeDagLayout(plan?.milestones ?? []);
  const selectedMilestone = plan?.milestones.find((milestone) => milestone.id === selectedMilestoneId) ?? null;

  const linkedSteps = (plan?.steps ?? [])
    .filter((s) => selectedMilestone ? s.milestone_id === selectedMilestone.id : false)
    .sort((a, b) => a.order - b.order);
  const goalSteps = (plan?.steps ?? []).filter((s) => !s.milestone_id);
  const canEditSelectedMilestoneSteps = selectedMilestone?.status === "active";
  const canCompleteSelectedMilestone = Boolean(
    selectedMilestone &&
      selectedMilestone.status === "active" &&
      linkedSteps.every((step) => step.completed),
  );

  let selectedMilestoneHint = "Click a milestone to see the steps that produce its outcome";
  if (selectedMilestone?.status === "pending") {
    selectedMilestoneHint = "Waiting for prerequisite milestone outcomes to be completed";
  } else if (selectedMilestone?.status === "active") {
    selectedMilestoneHint = canCompleteSelectedMilestone
      ? "All linked steps are done. Mark the milestone complete once you can clearly see the result is in place."
      : "Mark steps as done as you finish them. Complete the milestone only once its result is clearly visible.";
  } else if (selectedMilestone?.status === "done") {
    selectedMilestoneHint = "This milestone outcome has been achieved";
  } else if (selectedMilestone?.status === "blocked") {
    selectedMilestoneHint = "This milestone outcome is currently blocked";
  }

  const completedCount = plan?.milestones.filter((m) => m.status === "done").length ?? 0;
  const totalCount = plan?.milestones.length ?? 0;
  const pct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  // Canvas dimensions based on computed positions
  const allPositions = Array.from(positions.values());
  const canvasWidth = Math.max(700, ...allPositions.map((p) => p.x + 250));
  const canvasHeight = Math.max(650, ...allPositions.map((p) => p.y + 200));

  return (
    <div className="bg-surface text-on-surface font-body h-screen overflow-hidden">
      <TopNavBar />

      <main className="mt-16 flex h-[calc(100vh-64px)] overflow-hidden">
        {/* Left goal sidebar */}
        <aside className="w-[300px] h-full self-start flex-shrink-0 border-r-4 border-black bg-stone-100">
          <div className="h-full overflow-y-auto px-3 py-3">
            {goal ? (
              <GoalSummaryPanel goal={goal} />
            ) : (
              <div className="bg-white border-4 border-black p-5 shadow-neobrutal-lg">
                <p className="font-headline font-black text-2xl uppercase animate-pulse">
                  Loading Goal...
                </p>
              </div>
            )}
          </div>
        </aside>

        {/* Graph canvas */}
        <section className="flex-1 min-w-0 border-r-4 border-black bg-surface flex flex-col">
          <div className="px-8 pt-8 pb-6 flex-shrink-0">
            {/* Plan header */}
            <div className="flex justify-between items-start gap-4">
              <div className="min-w-0 flex-1">
                <h1 className="font-headline font-black text-3xl uppercase tracking-tighter break-words">
                  {goal?.title ?? "Plan"}
                </h1>
                <div className="flex gap-4 mt-2 flex-wrap">
                  <span className="bg-black text-white font-mono text-[10px] px-2 py-0.5 uppercase">
                    ID: {id?.toUpperCase()}
                  </span>
                  <span className="font-mono text-[10px] text-gray-500 uppercase">
                    MODE: DAG_DEPENDENCY
                  </span>
                </div>
              </div>
              <div className="bg-white border-2 border-black p-4 shadow-neobrutal">
                <h4 className="font-headline font-bold text-[10px] uppercase text-gray-500 mb-1">Progress</h4>
                <div className="flex items-end gap-2">
                  <span className="font-headline font-black text-2xl">{pct}%</span>
                  <span className="font-mono text-[10px] mb-1">
                    {completedCount}/{totalCount} MILESTONES
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0 overflow-auto">
            <div
              className="blueprint-grid relative px-8 pb-8 min-w-full min-h-full"
              style={{
                width: Math.max(canvasWidth + 64, 900),
                height: Math.max(canvasHeight + 32, 700),
              }}
            >
              {/* Milestone graph */}
              {isLoading ? (
                <div className="flex items-center justify-center h-64">
                  <div className="font-headline font-black text-2xl uppercase animate-pulse">
                    Rendering System Graph...
                  </div>
                </div>
              ) : (
                <div
                  className="relative"
                  style={{ width: canvasWidth, height: canvasHeight }}
                >
                  <MilestoneConnectors milestones={plan?.milestones ?? []} positions={positions} />
                  {plan?.milestones.map((milestone) => (
                    <NodeCard
                      key={milestone.id}
                      milestone={milestone}
                      position={positions.get(milestone.id) ?? { x: 0, y: 0 }}
                      isSelected={selectedMilestone?.id === milestone.id}
                      onClick={() =>
                        setSelectedMilestoneId((prev) => (prev === milestone.id ? null : milestone.id))
                      }
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Right sidebar */}
        <section className="w-[400px] flex-shrink-0 h-full min-h-0 flex flex-col bg-stone-50 overflow-hidden">
          {/* Sidebar header */}
          <div className="p-6 bg-black text-white">
            <div className="flex justify-between items-start mb-4">
              <span className="font-mono text-[10px] tracking-widest uppercase opacity-60">
                Selected_Node
              </span>
              {selectedMilestone && (
                <button
                  onClick={() => setSelectedMilestoneId(null)}
                  className="material-symbols-outlined text-sm opacity-60 hover:opacity-100"
                >
                  close
                </button>
              )}
            </div>
            <h2 className="font-headline font-black text-2xl uppercase leading-none">
              {selectedMilestone
                ? `${selectedMilestone.node_id}_${selectedMilestone.title.replace(/\s+/g, "_").toUpperCase()}`
                : "SELECT_A_NODE"}
            </h2>
            <p className="text-[10px] font-mono mt-2 text-primary-fixed uppercase tracking-tight">
              {selectedMilestone
                ? `${selectedMilestone.status.toUpperCase()} Milestone Context`
                : selectedMilestoneHint}
            </p>
            {selectedMilestone?.description && (
              <p className="text-[10px] font-mono mt-2 text-gray-300 normal-case leading-relaxed">
                {selectedMilestone.description}
              </p>
            )}
            {selectedMilestone && (
              <p className="text-[10px] font-mono mt-2 text-gray-300 uppercase tracking-tight">
                {selectedMilestoneHint}
              </p>
            )}
          </div>

          {/* Task list */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-4">
            {selectedMilestone && linkedSteps.length > 0 && (
              <div>
                <h4 className="font-headline font-bold text-[10px] uppercase text-gray-400 mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 bg-secondary-container inline-block" />
                  Linked Tasks ({selectedMilestone.node_id})
                </h4>
                <ul className="space-y-3">
                  {linkedSteps.map((step) => (
                    <TaskItem
                      key={step.id}
                      step={step}
                      goalId={id!}
                      disabled={!canEditSelectedMilestoneSteps}
                    />
                  ))}
                </ul>
              </div>
            )}

            {selectedMilestone && linkedSteps.length === 0 && (
              <div className="text-center py-8 border-2 border-dashed border-gray-200">
                <span className="material-symbols-outlined text-3xl text-gray-300 block mb-2">
                  checklist
                </span>
                <p className="font-headline font-bold text-xs uppercase text-gray-400">
                  No tasks linked to this milestone
                </p>
              </div>
            )}

            {/* Goal-level tasks */}
            <div className={selectedMilestone ? "pt-4 border-t-2 border-dashed border-black" : ""}>
              <h4 className="font-headline font-bold text-[10px] uppercase text-gray-400 mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-xs">public</span>
                Goal Tasks
              </h4>
              {goalSteps.length === 0 ? (
                <p className="font-mono text-[10px] text-gray-400 uppercase">No goal-level tasks</p>
              ) : (
                <ul className="space-y-3">
                  {goalSteps.map((step) => (
                    <TaskItem key={step.id} step={step} goalId={id!} disabled={false} />
                  ))}
                </ul>
              )}
            </div>

            {/* Goal metadata */}
            {goal && (
              <div className="pt-4 border-t-2 border-dashed border-black">
                <h4 className="font-headline font-bold text-[10px] uppercase text-gray-400 mb-3">
                  Goal Context
                </h4>
                <div className="bg-white border-2 border-black p-3">
                  <p className="font-headline font-bold text-xs uppercase">{goal.title}</p>
                  {goal.due_date && (
                    <p className="font-mono text-[9px] text-gray-500 mt-1 uppercase">
                      Due: {new Date(goal.due_date).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Footer CTA */}
          <div className="p-4 bg-white border-t-4 border-black">
            {selectedMilestone && (
              <button
                onClick={() => completeMilestone()}
                disabled={!canCompleteSelectedMilestone || isCompletingMilestone}
                className="w-full mb-3 bg-secondary-container border-4 border-black p-4 font-headline font-black text-sm uppercase disabled:opacity-50 disabled:cursor-not-allowed shadow-neobrutal"
              >
                Complete Milestone
              </button>
            )}
            {showBlockerInput ? (
              <div className="flex flex-col gap-2">
                <input
                  type="text"
                  value={blockerText}
                  onChange={(e) => setBlockerText(e.target.value)}
                  placeholder="Describe what came up..."
                  className="w-full border-2 border-black p-3 font-mono text-sm focus:outline-none focus:bg-secondary-container"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => reportBlocker()}
                    disabled={!blockerText.trim() || isReporting}
                    className="flex-1 bg-tertiary text-white border-2 border-black p-3 font-headline font-black text-xs uppercase hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    Report Blocker
                  </button>
                  <button
                    onClick={() => { setShowBlockerInput(false); setBlockerText(""); }}
                    className="border-2 border-black p-3 font-headline font-bold text-xs uppercase hover:bg-surface-container"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowBlockerInput(true)}
                className="w-full bg-[#FFD700] border-4 border-black p-4 font-headline font-black text-sm uppercase hover:bg-black hover:text-[#FFD700] transition-all shadow-neobrutal flex items-center justify-center gap-2 group active:translate-y-1 active:shadow-none"
              >
                <span className="material-symbols-outlined font-black group-hover:scale-110 transition-transform">
                  priority_high
                </span>
                Something Came Up
              </button>
            )}
          </div>
        </section>

      </main>
    </div>
  );
}
