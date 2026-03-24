export type GoalStatus =
  | "drafting"
  | "clarifying"
  | "planning"
  | "active"
  | "blocked"
  | "done"
  | "archived";

export type MilestoneStatus = "pending" | "active" | "blocked" | "done";

export interface Goal {
  id: string;
  user_id: string;
  title: string;
  description: string;
  synopsis: string;
  time_constraints: string[];
  resources: string[];
  current_state: string[];
  success_criteria: string[];
  risks_or_unknowns: string[];
  status: GoalStatus;
  milestones_total: number;
  milestones_completed: number;
  due_date: string | null;
  created_at: string;
  blocker_reason: string | null;
}

export interface ClarifyingQuestion {
  id: string;
  goal_id: string;
  node_id: string;
  icon: string;
  question: string;
  answer: string | null;
  round: number;
}

export interface Milestone {
  id: string;
  goal_id: string;
  node_id: string;
  title: string;
  description: string;
  status: MilestoneStatus;
  depends_on: string[];
  steps_total: number;
  steps_completed: number;
  blocker_reason: string | null;
}

export interface Step {
  id: string;
  goal_id: string;
  milestone_id: string | null;
  title: string;
  completed: boolean;
  priority: string;
  recurring: boolean;
  order: number;
}

export interface Plan {
  goal_id: string;
  milestones: Milestone[];
  steps: Step[];
}

export interface CreateGoalResponse {
  goal: Goal;
  questions: ClarifyingQuestion[];
}

export interface AnswerItem {
  question_id: string;
  answer: string;
}

export interface SubmitAnswersResponse {
  status: "needs_more_questions" | "ready";
  questions: ClarifyingQuestion[];
  goal: Goal | null;
}
