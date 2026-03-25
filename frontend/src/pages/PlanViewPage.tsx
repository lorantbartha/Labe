import { memo, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { goalsApi } from "../api/goals";
import TopNavBar from "../components/layout/TopNavBar";
import type { Goal, Milestone, MilestoneStatus, Step } from "../types";
import {
  computeDagLayout,
  DAG_LAYER_GAP,
  DAG_NODE_MIN_HEIGHT,
  DAG_NODE_WIDTH,
  type Position,
} from "../utils/dagLayout";

const MILESTONE_STYLES: Record<MilestoneStatus, { card: string; text: string; icon: string }> = {
  done: { card: "bg-green-500 border-4 border-black", text: "text-black", icon: "check_circle" },
  active: { card: "bg-secondary-container border-4 border-black ring-4 ring-black ring-offset-2", text: "text-black", icon: "radio_button_checked" },
  blocked: { card: "bg-error-container border-4 border-black", text: "text-on-error", icon: "block" },
  pending: { card: "bg-white border-4 border-black border-dashed", text: "text-gray-400", icon: "star" },
};

const EDGE_ARROW_GAP = 8;

interface NodeCardProps {
  milestone: Milestone;
  dependencyNodeIds: string[];
  position: Position;
  minHeight: number;
  isSelected: boolean;
  onClick: () => void;
  onMeasure: (milestoneId: string, height: number) => void;
}

function NodeCard({ milestone, dependencyNodeIds, position, minHeight, isSelected, onClick, onMeasure }: NodeCardProps) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const style = MILESTONE_STYLES[milestone.status];
  const pct = milestone.steps_total > 0
    ? Math.round((milestone.steps_completed / milestone.steps_total) * 100)
    : 0;

  useLayoutEffect(() => {
    if (nodeRef.current) {
      onMeasure(milestone.id, nodeRef.current.offsetHeight);
    }
  }, [
    dependencyNodeIds,
    milestone.blocker_reason,
    milestone.description,
    milestone.id,
    milestone.status,
    milestone.steps_completed,
    milestone.steps_total,
    milestone.title,
    onMeasure,
  ]);

  return (
    <div
      className={`absolute cursor-pointer group transition-transform hover:-translate-y-1 ${isSelected ? "ring-4 ring-offset-2 ring-black" : ""}`}
      ref={nodeRef}
      style={{ left: position.x, top: position.y, width: DAG_NODE_WIDTH, minHeight, zIndex: 10 }}
      onClick={onClick}
    >
      <div className={`${style.card} p-4 shadow-neobrutal flex min-h-full flex-col`}>
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
          <p className={`font-mono text-[9px] mt-2 flex-1 ${style.text} opacity-70 leading-snug normal-case`}>
            {milestone.description}
          </p>
        )}
        <p className={`font-mono text-[8px] mt-2 uppercase tracking-tight ${style.text} opacity-65`}>
          {dependencyNodeIds.length > 0 ? `Depends on: ${dependencyNodeIds.join(", ")}` : "Root milestone"}
        </p>
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

const MilestoneConnectors = memo(function MilestoneConnectors({
  milestones,
  positions,
  measuredHeights,
}: {
  milestones: Milestone[];
  positions: Map<string, Position>;
  measuredHeights: Map<string, number>;
}) {
  const layerByMilestoneId = new Map<string, number>();
  const layerTop = new Map<number, number>();
  const layerBottom = new Map<number, number>();
  for (const milestone of milestones) {
    const position = positions.get(milestone.id);
    if (!position) continue;
    const layer = Math.round((position.y - 40) / (DAG_NODE_MIN_HEIGHT + DAG_LAYER_GAP));
    const height = measuredHeights.get(milestone.id) ?? DAG_NODE_MIN_HEIGHT;
    layerByMilestoneId.set(milestone.id, layer);
    layerTop.set(layer, Math.min(layerTop.get(layer) ?? position.y, position.y));
    layerBottom.set(layer, Math.max(layerBottom.get(layer) ?? position.y + height, position.y + height));
  }
  const lines: {
    startX: number;
    startY: number;
    laneY: number;
    endX: number;
    endY: number;
    key: string;
  }[] = [];
  for (const m of milestones) {
    const mPos = positions.get(m.id);
    if (!mPos) continue;
    const sortedDeps = [...m.depends_on].sort((a, b) => {
      const aPos = positions.get(a);
      const bPos = positions.get(b);
      return (aPos?.x ?? 0) - (bPos?.x ?? 0);
    });
    for (const [depIndex, depId] of sortedDeps.entries()) {
      const depPos = positions.get(depId);
      if (!depPos) continue;
      const depLayer = layerByMilestoneId.get(depId) ?? 0;
      const childLayer = layerByMilestoneId.get(m.id) ?? depLayer + 1;
      const depHeight = measuredHeights.get(depId) ?? DAG_NODE_MIN_HEIGHT;
      const startX = depPos.x + DAG_NODE_WIDTH / 2;
      const startY = depPos.y + depHeight;
      const endX = mPos.x + DAG_NODE_WIDTH / 2;
      const endY = mPos.y - EDGE_ARROW_GAP;
      const corridorTop = (layerBottom.get(depLayer) ?? startY) + 10;
      const corridorBottom = (layerTop.get(childLayer) ?? mPos.y) - 10;
      const baseLaneY = corridorTop < corridorBottom
        ? corridorTop + (corridorBottom - corridorTop) / 2
        : startY + 24;
      const laneY = baseLaneY + (depIndex - (sortedDeps.length - 1) / 2) * 14;
      lines.push({ startX, startY, laneY, endX, endY, key: `${depId}-${m.id}` });
    }
  }

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="black" />
        </marker>
      </defs>
      {lines.map(({ startX, startY, laneY, endX, endY, key }) => (
        <g key={key}>
          <line x1={startX} y1={startY} x2={startX} y2={laneY} stroke="black" strokeWidth="2" />
          <line x1={startX} y1={laneY} x2={endX} y2={laneY} stroke="black" strokeWidth="2" />
          <line
            x1={endX} y1={laneY}
            x2={endX} y2={endY}
            stroke="black" strokeWidth="2"
            markerEnd="url(#arrowhead)"
          />
        </g>
      ))}
    </svg>
  );
});

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
  const [nodeHeights, setNodeHeights] = useState<Record<string, number>>({});
  const [adaptSummary, setAdaptSummary] = useState<string | null>(null);

  const handleNodeMeasure = (milestoneId: string, height: number) => {
    setNodeHeights((prev) => (prev[milestoneId] === height ? prev : { ...prev, [milestoneId]: height }));
  };

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

  const { mutate: adaptPlan, isPending: isAdapting } = useMutation({
    mutationFn: () => goalsApi.adaptPlan(id!, blockerText),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
      queryClient.invalidateQueries({ queryKey: ["goal", id] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      setShowBlockerInput(false);
      setBlockerText("");
      setAdaptSummary(data.summary);
    },
  });

  const { mutate: completeMilestone, isPending: isCompletingMilestone } = useMutation({
    mutationFn: () => goalsApi.finishMilestone(id!, selectedMilestoneId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
      queryClient.invalidateQueries({ queryKey: ["goal", id] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
    },
  });

  const positions = useMemo(() => computeDagLayout(plan?.milestones ?? []), [plan?.milestones]);
  const nodeIdByMilestoneId = new Map((plan?.milestones ?? []).map((milestone) => [milestone.id, milestone.node_id]));
  const measuredHeights = new Map(Object.entries(nodeHeights));
  const layerIndexByMilestoneId = new Map<string, number>();
  for (const [milestoneId, position] of positions) {
    layerIndexByMilestoneId.set(
      milestoneId,
      Math.round((position.y - 40) / (DAG_NODE_MIN_HEIGHT + DAG_LAYER_GAP)),
    );
  }
  const layerIds = Array.from(new Set(layerIndexByMilestoneId.values())).sort((a, b) => a - b);
  const extraOffsetByLayer = new Map<number, number>();
  let runningOffset = 0;
  for (const layerId of layerIds) {
    extraOffsetByLayer.set(layerId, runningOffset);
    const layerMilestones = (plan?.milestones ?? []).filter((milestone) => layerIndexByMilestoneId.get(milestone.id) === layerId);
    const maxHeight = Math.max(
      DAG_NODE_MIN_HEIGHT,
      ...layerMilestones.map((milestone) => measuredHeights.get(milestone.id) ?? DAG_NODE_MIN_HEIGHT),
    );
    runningOffset += Math.max(0, maxHeight - DAG_NODE_MIN_HEIGHT);
  }
  const adjustedPositions = new Map<string, Position>();
  for (const [milestoneId, position] of positions) {
    const layerId = layerIndexByMilestoneId.get(milestoneId) ?? 0;
    adjustedPositions.set(milestoneId, {
      x: position.x,
      y: position.y + (extraOffsetByLayer.get(layerId) ?? 0),
    });
  }
  const selectedMilestone = plan?.milestones.find((milestone) => milestone.id === selectedMilestoneId) ?? null;
  const selectedDependencyNodeIds = (selectedMilestone?.depends_on ?? [])
    .map((depId) => nodeIdByMilestoneId.get(depId))
    .filter((value): value is string => Boolean(value));

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
  const allPositions = Array.from(adjustedPositions.values());
  const canvasWidth = Math.max(820, ...allPositions.map((p) => p.x + DAG_NODE_WIDTH + 72));
  const canvasHeight = Math.max(
    680,
    ...(plan?.milestones ?? []).map((milestone) => {
      const position = adjustedPositions.get(milestone.id);
      const height = measuredHeights.get(milestone.id) ?? DAG_NODE_MIN_HEIGHT;
      return (position?.y ?? 0) + height + DAG_LAYER_GAP;
    }),
  );

  return (
    <div className="bg-surface text-on-surface font-body h-screen overflow-hidden">
      <TopNavBar />

      <main className="mt-16 flex h-[calc(100vh-64px)] overflow-hidden">
        {/* Left goal sidebar */}
        <aside className="w-[350px] h-full self-start flex-shrink-0 border-r-4 border-black bg-stone-100">
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
          {/* Adapt plan summary banner */}
          {adaptSummary && (
            <div className="flex-shrink-0 bg-[#FFD700] border-b-4 border-black px-6 py-3 flex items-start gap-3">
              <span className="material-symbols-outlined text-black font-black flex-shrink-0 mt-0.5">auto_awesome</span>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-xs text-black whitespace-pre-line leading-relaxed">{adaptSummary}</p>
              </div>
              <button
                onClick={() => setAdaptSummary(null)}
                className="flex-shrink-0 font-mono text-black text-xs uppercase hover:underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Adapting overlay */}
          {isAdapting && (
            <div className="flex-shrink-0 bg-black text-[#FFD700] border-b-4 border-[#FFD700] px-6 py-3 flex items-center gap-3">
              <span className="material-symbols-outlined animate-spin font-black">progress_activity</span>
              <span className="font-headline font-black text-xs uppercase tracking-wider">Adapting plan...</span>
            </div>
          )}

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
                  <MilestoneConnectors
                    milestones={plan?.milestones ?? []}
                    positions={adjustedPositions}
                    measuredHeights={measuredHeights}
                  />
                  {plan?.milestones.map((milestone) => (
                    <NodeCard
                      key={milestone.id}
                      milestone={milestone}
                      dependencyNodeIds={milestone.depends_on
                        .map((depId) => nodeIdByMilestoneId.get(depId))
                        .filter((value): value is string => Boolean(value))}
                      position={adjustedPositions.get(milestone.id) ?? { x: 0, y: 0 }}
                      minHeight={DAG_NODE_MIN_HEIGHT}
                      isSelected={selectedMilestone?.id === milestone.id}
                      onMeasure={handleNodeMeasure}
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
                {selectedDependencyNodeIds.length > 0
                  ? `Depends on: ${selectedDependencyNodeIds.join(", ")}`
                  : "Root milestone"}
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
                  placeholder="Describe what changed..."
                  className="w-full border-2 border-black p-3 font-mono text-sm focus:outline-none focus:bg-secondary-container"
                  autoFocus
                  onKeyDown={(e) => { if (e.key === "Enter" && blockerText.trim()) adaptPlan(); }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => adaptPlan()}
                    disabled={!blockerText.trim() || isAdapting}
                    className="flex-1 bg-tertiary text-white border-2 border-black p-3 font-headline font-black text-xs uppercase hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {isAdapting ? "Adapting..." : "Adapt Plan"}
                  </button>
                  <button
                    onClick={() => { setShowBlockerInput(false); setBlockerText(""); }}
                    disabled={isAdapting}
                    className="border-2 border-black p-3 font-headline font-bold text-xs uppercase hover:bg-surface-container disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowBlockerInput(true)}
                title="Tell us what has changed that may influence our plans"
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
