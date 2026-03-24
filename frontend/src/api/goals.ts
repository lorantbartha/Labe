import type {
  AnswerItem,
  ClarifyingQuestion,
  CreateGoalResponse,
  Goal,
  Milestone,
  MilestoneStatus,
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

  updateMilestone: (goalId: string, milestoneId: string, status: MilestoneStatus) =>
    request<Milestone>(`/goals/${goalId}/milestones/${milestoneId}`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),

  updateStep: (goalId: string, stepId: string, completed: boolean) =>
    request<Step>(`/goals/${goalId}/steps/${stepId}`, {
      method: "PUT",
      body: JSON.stringify({ completed }),
    }),

  reportBlocker: (goalId: string, description: string) =>
    request<Goal>(`/goals/${goalId}/blockers`, {
      method: "POST",
      body: JSON.stringify({ description }),
    }),

  archiveGoal: (goalId: string) =>
    request<Goal>(`/goals/${goalId}/archive`, { method: "POST" }),
};
