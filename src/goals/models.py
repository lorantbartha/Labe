from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class GoalStatus(StrEnum):
    drafting = "drafting"
    clarifying = "clarifying"
    planning = "planning"
    active = "active"
    blocked = "blocked"
    done = "done"
    archived = "archived"


class MilestoneStatus(StrEnum):
    pending = "pending"
    active = "active"
    blocked = "blocked"
    done = "done"


class Goal(BaseModel):
    id: str
    user_id: str = "default"
    title: str
    description: str = ""
    synopsis: str = ""
    time_constraints: list[str] = []
    resources: list[str] = []
    current_state: list[str] = []
    success_criteria: list[str] = []
    risks_or_unknowns: list[str] = []
    status: GoalStatus
    milestones_total: int
    milestones_completed: int
    due_date: str | None = None
    created_at: str
    blocker_reason: str | None = None


class ClarifyingQuestion(BaseModel):
    id: str
    goal_id: str
    node_id: str
    icon: str
    question: str
    answer: str | None = None
    round: int = 1


class Milestone(BaseModel):
    id: str
    goal_id: str
    node_id: str
    title: str
    description: str = ""
    status: MilestoneStatus
    depends_on: list[str] = []
    steps_total: int
    steps_completed: int
    blocker_reason: str | None = None


class Step(BaseModel):
    id: str
    goal_id: str
    milestone_id: str | None = None
    title: str
    completed: bool
    priority: Literal["normal", "high"] = "normal"
    recurring: bool = False
    order: int = 0


class Plan(BaseModel):
    goal_id: str
    milestones: list[Milestone]
    steps: list[Step]


# --- Request / Response models ---


class CreateGoalRequest(BaseModel):
    description: str


class CreateGoalResponse(BaseModel):
    goal: Goal
    questions: list[ClarifyingQuestion]


class AnswerItem(BaseModel):
    question_id: str
    answer: str


class SubmitAnswersRequest(BaseModel):
    answers: list[AnswerItem]


class SubmitAnswersResponse(BaseModel):
    status: Literal["needs_more_questions", "ready"]
    questions: list[ClarifyingQuestion] = []
    goal: Goal | None = None


class UpdateMilestoneRequest(BaseModel):
    status: MilestoneStatus


class UpdateStepRequest(BaseModel):
    completed: bool


class ReportBlockerRequest(BaseModel):
    description: str
