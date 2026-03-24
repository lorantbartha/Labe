import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { goalsApi } from "../api/goals";
import SideNavBar from "../components/layout/SideNavBar";
import TopNavBar from "../components/layout/TopNavBar";
import type { ClarifyingQuestion } from "../types";

const NODE_STYLES = [
  "bg-primary text-white",
  "bg-tertiary text-white",
  "bg-primary-container text-black",
];

type SubmissionPhase = "idle" | "submitting_answers" | "generating_plan";

export default function ClarifyingQAPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [allQuestions, setAllQuestions] = useState<ClarifyingQuestion[]>([]);
  const [submissionPhase, setSubmissionPhase] = useState<SubmissionPhase>("idle");
  const [newQuestionIds, setNewQuestionIds] = useState<string[]>([]);
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const { data: goal } = useQuery({
    queryKey: ["goal", id],
    queryFn: () => goalsApi.get(id!),
    enabled: !!id,
  });

  const { isLoading } = useQuery({
    queryKey: ["questions", id],
    queryFn: () => goalsApi.getQuestions(id!),
    enabled: !!id,
    // Populate allQuestions once on initial load
    select: (data) => data,
  });

  const { data: initialQuestions } = useQuery({
    queryKey: ["questions", id],
    queryFn: () => goalsApi.getQuestions(id!),
    enabled: !!id,
  });

  useEffect(() => {
    if (initialQuestions && allQuestions.length === 0) {
      setAllQuestions(initialQuestions);
      // Pre-fill any already-answered questions
      const prefilled: Record<string, string> = {};
      for (const q of initialQuestions) {
        if (q.answer) prefilled[q.id] = q.answer;
      }
      if (Object.keys(prefilled).length > 0) {
        setAnswers((prev) => ({ ...prefilled, ...prev }));
      }
    }
  }, [initialQuestions, allQuestions.length]);

  const unansweredQuestions = allQuestions.filter((q) => !(answers[q.id] ?? "").trim());
  const allCurrentAnswered = allQuestions.length > 0 && unansweredQuestions.length === 0;
  const answeredCount = allQuestions.filter((q) => (answers[q.id] ?? "").trim() !== "").length;

  const { mutate: submitAnswers, isPending: isSubmitting } = useMutation({
    mutationFn: () =>
      goalsApi.submitAnswers(
        id!,
        allQuestions
          .filter((q) => (answers[q.id] ?? "").trim())
          .map((q) => ({ question_id: q.id, answer: answers[q.id] }))
      ),
    onSuccess: async (response) => {
      if (response.status === "needs_more_questions") {
        setAllQuestions((prev) => [...prev, ...response.questions]);
        setNewQuestionIds(response.questions.map((question) => question.id));
        setSubmissionPhase("idle");
      } else {
        // ready — generate plan then navigate
        setSubmissionPhase("generating_plan");
        await goalsApi.generatePlan(id!);
        queryClient.invalidateQueries({ queryKey: ["goals"] });
        navigate(`/goals/${id}/plan`);
      }
    },
    onError: () => {
      setSubmissionPhase("idle");
    },
  });

  const currentRound = allQuestions.length > 0 ? Math.max(...allQuestions.map((q) => q.round)) : 1;
  const isGeneratingPlan = submissionPhase === "generating_plan";
  const isSubmittingAnswers = submissionPhase === "submitting_answers" || (isSubmitting && !isGeneratingPlan);

  useEffect(() => {
    if (newQuestionIds.length === 0) {
      return;
    }
    const firstNewQuestionId = newQuestionIds[0];
    const input = inputRefs.current[firstNewQuestionId];
    if (!input) {
      return;
    }
    input.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => input.focus(), 250);
    setNewQuestionIds([]);
  }, [allQuestions, newQuestionIds]);

  return (
    <div className="bg-surface font-body text-on-surface min-h-screen selection:bg-secondary-container">
      <TopNavBar />
      <SideNavBar />

      <main className="ml-64 pt-16 min-h-screen blueprint-pattern">
        {/* Context header */}
        <section className="w-full bg-surface-container-high border-b-4 border-black px-8 py-6 flex items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold font-headline uppercase tracking-widest text-on-surface-variant">
              System Context // Identity Anchor
            </span>
            <h1 className="font-headline font-extrabold text-2xl uppercase leading-none">
              YOUR GOAL:{" "}
              <span className="font-normal normal-case tracking-normal">
                {goal?.title ?? "Loading..."}
              </span>
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {currentRound > 1 && (
              <div className="border-2 border-black px-3 py-1.5 font-headline font-bold text-xs uppercase shadow-neobrutal bg-tertiary text-white flex-shrink-0">
                ROUND {currentRound}
              </div>
            )}
            {allQuestions.length > 0 && (
              <div
                className={[
                  "border-2 border-black px-4 py-1.5 font-headline font-bold text-xs uppercase shadow-neobrutal tracking-tight flex-shrink-0",
                  allCurrentAnswered ? "bg-green-accent text-black" : "bg-secondary-container text-black",
                ].join(" ")}
              >
                CLARIFYING CONSTRAINTS — {answeredCount} of {allQuestions.length} ANSWERED
              </div>
            )}
          </div>
        </section>

        <div className="max-w-4xl mx-auto px-6 py-12">
          {isLoading ? (
            <div className="text-center py-24">
              <div className="font-headline font-black text-2xl uppercase tracking-tighter animate-pulse">
                Loading Questions...
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-12">
              {allQuestions.map((question, idx) => {
                const isAnswered = (answers[question.id] ?? "").trim() !== "";
                const isFromPreviousRound = question.round < currentRound;
                const isNewQuestion = newQuestionIds.includes(question.id);
                return (
                  <div key={question.id} className="relative">
                    <div
                      className={`absolute -top-4 -left-4 ${NODE_STYLES[idx % NODE_STYLES.length]} border-2 border-black px-3 py-1 font-headline font-black text-sm z-10 shadow-neobrutal`}
                    >
                      {question.node_id}
                    </div>
                    {isNewQuestion && (
                      <div className="absolute -top-4 right-6 bg-black text-white border-2 border-black px-3 py-1 font-headline font-black text-[10px] uppercase z-10 shadow-neobrutal animate-pulse">
                        New Round
                      </div>
                    )}
                    <div className={`border-4 border-black p-8 shadow-neobrutal ${isFromPreviousRound && isAnswered ? "bg-surface-container opacity-70" : "bg-white"}`}>
                      <div className="flex items-start gap-4 mb-6">
                        <span className="material-symbols-outlined text-3xl text-primary-dim">
                          {question.icon}
                        </span>
                        <h3 className="font-headline font-bold text-2xl uppercase tracking-tight">
                          {question.question}
                        </h3>
                      </div>
                      <div className="space-y-4">
                        <label className="block font-headline font-bold text-[10px] uppercase tracking-tighter text-on-surface-variant">
                          User Logic Input
                        </label>
                        <input
                          type="text"
                          value={answers[question.id] ?? ""}
                          onChange={(e) =>
                            setAnswers((prev) => ({ ...prev, [question.id]: e.target.value }))
                          }
                          ref={(node) => {
                            inputRefs.current[question.id] = node;
                          }}
                          disabled={isFromPreviousRound && isAnswered}
                          className="w-full bg-surface border-2 border-black p-4 font-mono text-sm focus:outline-none focus:bg-secondary-container transition-colors placeholder:text-gray-400 disabled:opacity-60 disabled:cursor-not-allowed"
                          placeholder="Type your answer..."
                        />
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* CTA */}
              <div className="flex flex-col items-center justify-center pt-8 border-t-4 border-black border-dashed">
                <button
                  onClick={() => {
                    setSubmissionPhase("submitting_answers");
                    submitAnswers();
                  }}
                  disabled={!allCurrentAnswered || isSubmittingAnswers || isGeneratingPlan}
                  className={`w-full border-4 border-black px-12 py-6 font-headline font-black text-2xl uppercase tracking-tighter shadow-neobrutal transition-all flex items-center justify-center gap-4 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0 ${
                    isGeneratingPlan
                      ? "bg-black text-secondary-container animate-pulse"
                      : isSubmittingAnswers
                        ? "bg-tertiary text-white"
                        : "bg-secondary-container text-black hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-neobrutal-lg"
                  }`}
                >
                  {isGeneratingPlan
                    ? "SYNTHESIZING PLAN..."
                    : isSubmittingAnswers
                      ? "ANALYZING ANSWERS..."
                      : "SUBMIT ANSWERS"}
                  <span className={`material-symbols-outlined text-3xl ${isGeneratingPlan ? "animate-spin" : isSubmittingAnswers ? "animate-bounce" : ""}`}>
                    {isGeneratingPlan ? "progress_activity" : "terminal"}
                  </span>
                </button>
                <p className="mt-4 font-headline font-bold text-[10px] uppercase tracking-widest text-on-surface-variant">
                  {isGeneratingPlan
                    ? "Compiling milestone graph and task structure"
                    : isSubmittingAnswers
                      ? "Evaluating constraints and checking for missing context"
                      : "Execute architectural synthesis sequence v1.0"}
                </p>
              </div>
            </div>
          )}
        </div>

      </main>
    </div>
  );
}
