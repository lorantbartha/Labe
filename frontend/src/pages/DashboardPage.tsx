import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { goalsApi } from "../api/goals";
import SideNavBar from "../components/layout/SideNavBar";
import TopNavBar from "../components/layout/TopNavBar";
import GoalCard from "../components/ui/GoalCard";
import type { Goal, GoalStatus } from "../types";

type FilterOption = "ALL" | GoalStatus;

const FILTER_OPTIONS: { label: string; value: FilterOption }[] = [
  { label: "ALL", value: "ALL" },
  { label: "Drafting", value: "drafting" },
  { label: "Active", value: "active" },
  { label: "Blocked", value: "blocked" },
  { label: "Done", value: "done" },
  { label: "Archived", value: "archived" },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<FilterOption>("ALL");

  const { data: goals, isLoading, error } = useQuery({
    queryKey: ["goals"],
    queryFn: goalsApi.list,
  });

  const filtered: Goal[] =
    goals?.filter((g) => activeFilter === "ALL" || g.status === activeFilter) ?? [];

  return (
    <div className="min-h-screen bg-surface blueprint-pattern">
      <TopNavBar />
      <SideNavBar />

      <main className="pt-24 pb-12 px-6 ml-64">
        {/* Header section */}
        <section className="mb-10 flex items-end justify-between gap-6">
          <div>
            <h1 className="font-headline font-black text-6xl uppercase tracking-tighter leading-none mb-4">
              System_Goals
            </h1>
            <div className="flex flex-wrap gap-2">
              {FILTER_OPTIONS.map(({ label, value }) => (
                <button
                  key={value}
                  onClick={() => setActiveFilter(value)}
                  className={[
                    "px-3 py-1 font-headline font-bold text-[10px] uppercase transition-colors",
                    activeFilter === value
                      ? "bg-black text-white"
                      : "border-2 border-black hover:bg-secondary-container",
                  ].join(" ")}
                >
                  {activeFilter === value ? `Filter: ${label}` : label}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={() => navigate("/goals/new")}
            className="bg-secondary-container text-black border-4 border-black px-8 py-4 font-headline font-black text-xl uppercase shadow-neobrutal-lg hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] transition-all flex items-center gap-3"
          >
            <span className="material-symbols-outlined text-xl font-bold">add</span>
            NEW GOAL
          </button>
        </section>

        {/* Goals grid */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="font-headline font-black text-2xl uppercase tracking-tighter animate-pulse">
              Loading System...
            </div>
          </div>
        ) : error ? (
          <div className="bg-white border-4 border-tertiary p-8 shadow-neobrutal text-center">
            <span className="material-symbols-outlined text-4xl text-tertiary mb-4 block">error</span>
            <p className="font-headline font-bold text-lg uppercase">Connection Error</p>
            <p className="font-mono text-sm text-on-surface-variant mt-2">
              Could not reach the backend. Is it running?
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState onNewGoal={() => navigate("/goals/new")} />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {filtered.map((goal) => (
              <GoalCard key={goal.id} goal={goal} />
            ))}
          </div>
        )}

      </main>
    </div>
  );
}

function EmptyState({ onNewGoal }: { onNewGoal: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-96 border-4 border-dashed border-black bg-white">
      <span className="material-symbols-outlined text-7xl text-gray-300 mb-6">rocket_launch</span>
      <h2 className="font-headline font-black text-3xl uppercase tracking-tighter mb-2">
        No goals yet
      </h2>
      <p className="font-headline font-bold text-sm uppercase text-on-surface-variant mb-8">
        Define your first objective to initialize the system
      </p>
      <button
        onClick={onNewGoal}
        className="bg-secondary-container text-black border-4 border-black px-8 py-4 font-headline font-black text-lg uppercase shadow-neobrutal hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all flex items-center gap-3"
      >
        <span className="material-symbols-outlined">add</span>
        Create First Goal
      </button>
    </div>
  );
}
