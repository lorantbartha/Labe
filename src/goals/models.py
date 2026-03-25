from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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
    change_history: list[str] = []
    milestones: list[Milestone] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)

    def summary_fields(self) -> dict:
        return {
            "synopsis": self.synopsis,
            "time_constraints": self.time_constraints,
            "resources": self.resources,
            "current_state": self.current_state,
            "success_criteria": self.success_criteria,
            "risks_or_unknowns": self.risks_or_unknowns,
        }

    def recent_change_history(self, limit: int = 3) -> list[str]:
        return self.change_history[-limit:] if self.change_history else []

    def add_change_entry(self, summary: str) -> list[str]:
        entry = f"[{datetime.now(UTC).strftime('%Y-%m-%d')}] {summary}"
        return self.change_history + [entry]

    def milestone_by_id(self, milestone_id: str) -> Milestone | None:
        return next((m for m in self.milestones if m.id == milestone_id), None)

    def step_by_id(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def steps_for_milestone(self, milestone_id: str) -> list[Step]:
        return [s for s in self.steps if s.milestone_id == milestone_id]

    def recalculate(self) -> "Goal":
        """Recompute step counts, milestone statuses, and derived totals."""
        step_counts: dict[str, tuple[int, int]] = {}
        for step in self.steps:
            if step.milestone_id is None:
                continue
            total, completed = step_counts.get(step.milestone_id, (0, 0))
            step_counts[step.milestone_id] = (total + 1, completed + int(step.completed))

        by_id = {m.id: m for m in self.milestones}
        recalculated = []
        for milestone in self.milestones:
            total, completed = step_counts.get(milestone.id, (0, 0))
            m = milestone.model_copy(update={"steps_total": total, "steps_completed": completed})
            if m.status != MilestoneStatus.done:
                deps_done = all(by_id[d].status == MilestoneStatus.done for d in m.depends_on if d in by_id)
                if m.status == MilestoneStatus.pending and deps_done:
                    m = m.model_copy(update={"status": MilestoneStatus.active})
                elif m.status == MilestoneStatus.active and not deps_done:
                    m = m.model_copy(update={"status": MilestoneStatus.pending})
            recalculated.append(m)

        return self.model_copy(update={
            "milestones": recalculated,
            "milestones_total": len(recalculated),
            "milestones_completed": sum(1 for m in recalculated if m.status == MilestoneStatus.done),
        })

    def update_step(self, step_id: str, completed: bool) -> tuple["Goal", Step]:
        found = self.step_by_id(step_id)
        if found is None:
            raise ValueError(f"Step {step_id} not found")
        if found.milestone_id is not None:
            milestone = self.milestone_by_id(found.milestone_id)
            if milestone is None:
                raise ValueError("Milestone for step was not found")
            if milestone.status != MilestoneStatus.active:
                raise ValueError("Tasks can only be completed for active milestones")
        updated_step = found.model_copy(update={"completed": completed})
        updated_steps = [updated_step if s.id == step_id else s for s in self.steps]
        goal = self.model_copy(update={"steps": updated_steps}).recalculate()
        return goal, updated_step

    def finish_milestone(self, milestone_id: str) -> tuple["Goal", Milestone]:
        found = self.milestone_by_id(milestone_id)
        if not found:
            raise ValueError(f"Milestone {milestone_id} not found")
        if found.status != MilestoneStatus.active:
            raise ValueError(f"Milestone must be active to finish, but is {found.status}")
        if not all(
            m.status == MilestoneStatus.done
            for dep_id in found.depends_on
            if (m := self.milestone_by_id(dep_id)) is not None
        ):
            raise ValueError("Milestone dependencies must be completed first")
        if any(not s.completed for s in self.steps_for_milestone(milestone_id)):
            raise ValueError("All linked tasks must be completed before finishing a milestone")
        finished = found.model_copy(update={"status": MilestoneStatus.done})
        updated = [finished if m.id == milestone_id else m for m in self.milestones]
        goal = self.model_copy(update={"milestones": updated}).recalculate()
        return goal, finished


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


class UpdateStepRequest(BaseModel):
    completed: bool



class AdaptPlanRequest(BaseModel):
    message: str


class AdaptPlanResponse(BaseModel):
    plan: Plan
    summary: str
