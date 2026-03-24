import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { goalsApi } from "../api/goals";

export default function GoalCreationPage() {
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const { mutate: createGoal, isPending } = useMutation({
    mutationFn: (d: string) => goalsApi.create(d),
    onSuccess: ({ goal }) => {
      navigate(`/goals/${goal.id}/clarify`);
    },
  });

  function handleSubmit() {
    const trimmed = description.trim();
    if (!trimmed) return;
    createGoal(trimmed);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="bg-surface-container-lowest text-on-primary-fixed font-body blueprint-pattern min-h-screen flex flex-col">
      {/* Header */}
      <header className="fixed top-0 left-0 w-full p-8 z-50 pointer-events-none">
        <div className="flex justify-between items-start">
          <div className="flex flex-col">
            <span className="font-headline font-black text-3xl tracking-tighter uppercase leading-none">
              LABE_SYSTEM
            </span>
            <span className="font-headline font-bold text-[10px] tracking-widest text-outline uppercase mt-1">
              v1.0.4_BLUEPRINT
            </span>
          </div>
          <div className="pointer-events-auto">
            <button
              onClick={() => navigate("/goals")}
              className="w-12 h-12 border-2 border-black flex items-center justify-center bg-surface-container-lowest hover:bg-secondary-container transition-colors shadow-neobrutal active:translate-x-0.5 active:translate-y-0.5 active:shadow-[2px_2px_0px_0px_#000000]"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-grow flex items-center justify-center px-24">
        <div className="w-full max-w-5xl relative">
          <div className="absolute -top-12 -left-4 font-headline text-xs font-bold uppercase tracking-[0.2em] text-outline flex items-center gap-2">
            <span className="w-8 h-[2px] bg-black inline-block" />
            Input Terminal 001
          </div>

          <div className="flex flex-col gap-10">
            <h1 className="font-headline font-black text-8xl tracking-tight leading-[0.9] text-on-primary-fixed max-w-3xl">
              What do you want to achieve?
            </h1>

            {/* Textarea */}
            <div className="relative group">
              <div className="absolute inset-0 bg-black translate-x-3 translate-y-3 -z-10 transition-transform group-focus-within:translate-x-4 group-focus-within:translate-y-4" />
              <textarea
                ref={textareaRef}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full bg-surface-container-lowest border-[3px] border-black p-8 text-2xl font-headline font-bold focus:ring-0 focus:outline-none focus:bg-secondary-container transition-colors placeholder:text-outline-variant placeholder:font-normal placeholder:italic resize-none"
                placeholder="e.g., I want to raise a pre-seed round in 3 months. I'm a first-time founder with a B2B SaaS product and 2 design partners. No investor network yet."
                rows={6}
                disabled={isPending}
              />
              <div className="absolute bottom-4 right-4 flex gap-2">
                <span className="bg-black text-white font-label text-[10px] px-2 py-1 uppercase font-bold tracking-tighter">
                  Required_Field
                </span>
                <span className="border-2 border-black text-black font-label text-[10px] px-2 py-1 uppercase font-bold tracking-tighter">
                  {description.trim() ? "System_Check: Ready" : "System_Check: Waiting"}
                </span>
              </div>
            </div>

            {/* Secondary anchors */}
            <div className="flex flex-wrap gap-8 items-start opacity-60">
              <div className="flex gap-4">
                <div className="w-[2px] h-12 bg-black" />
                <div className="flex flex-col">
                  <span className="font-headline text-[10px] font-black uppercase tracking-widest">
                    Logic Stream
                  </span>
                  <span className="text-xs max-w-[200px] leading-tight mt-1">
                    Labe decomposes your vision into executable technical nodes.
                  </span>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-[2px] h-12 bg-black" />
                <div className="flex flex-col">
                  <span className="font-headline text-[10px] font-black uppercase tracking-widest">
                    Integrity Check
                  </span>
                  <span className="text-xs max-w-[200px] leading-tight mt-1">
                    High-density planning for complex architectural outcomes.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="p-12 flex justify-center items-end bg-transparent">
        <div className="w-full max-w-5xl flex items-center justify-between gap-8">
          {/* CTA */}
          <button
            onClick={handleSubmit}
            disabled={!description.trim() || isPending}
            className={`border-[4px] border-black px-12 py-6 font-headline font-black text-2xl tracking-tighter uppercase shadow-neobrutal-lg transition-all group flex items-center justify-center gap-4 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0 ${
              isPending
                ? "bg-black text-secondary-container animate-pulse"
                : "bg-secondary-fixed text-on-primary-fixed hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neobrutal-xl active:translate-y-1 active:translate-x-1 active:shadow-[2px_2px_0px_0px_#000000]"
            }`}
          >
            {isPending ? "CLARIFYING..." : "LET'S PLAN THIS"}
            <span className={`material-symbols-outlined text-3xl font-bold transition-transform ${isPending ? "animate-spin" : "group-hover:translate-x-2"}`}>
              {isPending ? "progress_activity" : "arrow_right_alt"}
            </span>
          </button>

          {/* Keyboard hint */}
          <div className="flex flex-col items-end">
            <span className="font-headline text-[9px] font-bold text-outline uppercase tracking-[0.3em]">
              {isPending ? "System_Status" : "Command_Prompt"}
            </span>
            <span className="font-body text-xs font-bold opacity-40 italic">
              {isPending ? "Generating title and first clarifying questions" : "Press CMD + Enter to initialize"}
            </span>
          </div>
        </div>
      </footer>

      {/* Blueprint accents */}
      <div className="fixed top-0 right-1/4 w-[1px] h-full bg-outline opacity-10 pointer-events-none -z-20" />
      <div className="fixed top-1/3 left-0 w-full h-[1px] bg-outline opacity-10 pointer-events-none -z-20" />
      <div className="fixed bottom-12 left-12 w-32 h-32 border-l-4 border-b-4 border-black opacity-10 pointer-events-none -z-20" />
      <div className="fixed top-12 right-12 w-32 h-32 border-r-4 border-t-4 border-black opacity-10 pointer-events-none -z-20" />
    </div>
  );
}
