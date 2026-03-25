import type {
  AdaptPlanResponse,
  AnswerItem,
  ClarifyingQuestion,
  CreateGoalResponse,
  Goal,
  Milestone,
  Plan,
  Step,
  SubmitAnswersResponse,
} from "../types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const goalsApi = {
  list: () => request<Goal[]>("/goals"),

  get: (id: string) => request<Goal>(`/goals/${id}`),

  create: (description: string) =>
    request<CreateGoalResponse>("/goals", {
      method: "POST",
      body: JSON.stringify({ description }),
    }),

  getQuestions: (id: string) =>
    request<ClarifyingQuestion[]>(`/goals/${id}/questions`),

  submitAnswers: (id: string, answers: AnswerItem[]) =>
    request<SubmitAnswersResponse>(`/goals/${id}/questions/answers`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  generatePlan: (id: string) =>
    request<Goal>(`/goals/${id}/plan/generate`, { method: "POST" }),

  getPlan: (id: string) => request<Plan>(`/goals/${id}/plan`),

  finishMilestone: (goalId: string, milestoneId: string) =>
    request<Milestone>(`/goals/${goalId}/milestones/${milestoneId}/finish`, { method: "POST" }),

  updateStep: (goalId: string, stepId: string, completed: boolean) =>
    request<Step>(`/goals/${goalId}/steps/${stepId}`, {
      method: "PUT",
      body: JSON.stringify({ completed }),
    }),

  adaptPlan: (goalId: string, message: string) =>
    request<AdaptPlanResponse>(`/goals/${goalId}/plan/adapt`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  archiveGoal: (goalId: string) =>
    request<Goal>(`/goals/${goalId}/archive`, { method: "POST" }),
};
