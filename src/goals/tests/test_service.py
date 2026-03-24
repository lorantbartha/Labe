import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOALS_TABLE", "test-goals")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from goals.models import AnswerItem, ClarifyingQuestion, Goal, GoalStatus, Milestone, MilestoneStatus, Step
from goals.service import GoalsService


@dataclass
class FakeGoalsRepository:
    goal: Goal
    questions: list = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    async def list_goals(self, user_id: str) -> list[Goal]:
        return [self.goal]

    async def get_goal(self, goal_id: str, user_id: str) -> Goal | None:
        return self.goal if self.goal.id == goal_id else None

    async def put_goal(self, goal: Goal, user_id: str) -> None:
        self.goal = goal

    async def get_questions(self, goal_id: str, user_id: str) -> list:
        return self.questions

    async def put_questions(self, goal_id: str, questions: list, user_id: str) -> None:
        self.questions = questions

    async def put_milestones_and_steps(
        self,
        goal_id: str,
        milestones: list[Milestone],
        steps: list[Step],
        user_id: str,
    ) -> None:
        self.milestones = milestones
        self.steps = steps

    async def get_milestones(self, goal_id: str, user_id: str) -> list[Milestone] | None:
        return self.milestones

    async def get_steps(self, goal_id: str, user_id: str) -> list[Step] | None:
        return self.steps

    async def update_goal_fields(self, goal_id: str, fields: dict, user_id: str) -> Goal | None:
        self.goal = self.goal.model_copy(update=fields)
        return self.goal


@dataclass
class FakeGoalsAI:
    async def generate_questions(self, goal_id: str, description: str) -> tuple[str, list]:
        return "Goal", []

    async def evaluate_sufficiency(
        self,
        goal_id: str,
        description: str,
        qa_pairs: list[tuple[str, str]],
        next_question_index: int,
        current_round: int,
    ) -> tuple[bool, list, object]:
        return True, [], type(
            "Summary",
            (),
            {
                "synopsis": "Short summary",
                "time_constraints": ["10 hours per week"],
                "resources": ["Laptop"],
                "current_state": ["Starting from scratch"],
                "success_criteria": ["First usable version shipped"],
                "risks_or_unknowns": ["Need user feedback"],
            },
        )()

    async def generate_plan(self, goal_id: str, goal: Goal, qa_pairs: list[tuple[str, str]]) -> tuple[list, list]:
        raise NotImplementedError


def make_service(milestones: list[Milestone], steps: list[Step]) -> tuple[GoalsService, FakeGoalsRepository]:
    goal = Goal(
        id="goal-1",
        user_id="default",
        title="Test Goal",
        description="Test Goal Description",
        status=GoalStatus.active,
        milestones_total=len(milestones),
        milestones_completed=sum(1 for milestone in milestones if milestone.status == MilestoneStatus.done),
        created_at="2026-03-24T00:00:00+00:00",
    )
    repo = FakeGoalsRepository(goal=goal, milestones=milestones, steps=steps)
    return GoalsService(goals_repo=repo, goals_ai=FakeGoalsAI()), repo


def make_question() -> ClarifyingQuestion:
    return ClarifyingQuestion(
        id="q1",
        goal_id="goal-1",
        node_id="NODE_001",
        icon="schedule",
        question="How much time do you have each week?",
        answer=None,
        round=1,
    )


@pytest.mark.asyncio
async def test_update_step_recalculates_milestone_progress() -> None:
    milestone = Milestone(
        id="m1",
        goal_id="goal-1",
        node_id="M-01",
        title="Milestone",
        status=MilestoneStatus.active,
        depends_on=[],
        steps_total=2,
        steps_completed=0,
    )
    steps = [
        Step(id="s1", goal_id="goal-1", milestone_id="m1", title="Step 1", completed=False),
        Step(id="s2", goal_id="goal-1", milestone_id="m1", title="Step 2", completed=False),
    ]
    service, repo = make_service([milestone], steps)

    updated = await service.update_step("goal-1", "s1", True, "default")

    assert updated is not None
    assert updated.completed is True
    assert repo.milestones[0].steps_total == 2
    assert repo.milestones[0].steps_completed == 1


@pytest.mark.asyncio
async def test_update_step_rejects_pending_milestone_tasks() -> None:
    milestone = Milestone(
        id="m1",
        goal_id="goal-1",
        node_id="M-01",
        title="Milestone",
        status=MilestoneStatus.pending,
        depends_on=["m0"],
        steps_total=1,
        steps_completed=0,
    )
    step = Step(id="s1", goal_id="goal-1", milestone_id="m1", title="Locked Step", completed=False)
    service, _ = make_service([milestone], [step])

    with pytest.raises(ValueError, match="active milestones"):
        await service.update_step("goal-1", "s1", True, "default")


@pytest.mark.asyncio
async def test_update_milestone_requires_all_steps_completed() -> None:
    milestone = Milestone(
        id="m1",
        goal_id="goal-1",
        node_id="M-01",
        title="Milestone",
        status=MilestoneStatus.active,
        depends_on=[],
        steps_total=2,
        steps_completed=1,
    )
    steps = [
        Step(id="s1", goal_id="goal-1", milestone_id="m1", title="Done Step", completed=True),
        Step(id="s2", goal_id="goal-1", milestone_id="m1", title="Open Step", completed=False),
    ]
    service, _ = make_service([milestone], steps)

    with pytest.raises(ValueError, match="All linked tasks"):
        await service.update_milestone("goal-1", "m1", MilestoneStatus.done, "default")


@pytest.mark.asyncio
async def test_marking_milestone_done_unlocks_dependents() -> None:
    root = Milestone(
        id="m1",
        goal_id="goal-1",
        node_id="M-01",
        title="Root",
        status=MilestoneStatus.active,
        depends_on=[],
        steps_total=1,
        steps_completed=1,
    )
    dependent = Milestone(
        id="m2",
        goal_id="goal-1",
        node_id="M-02",
        title="Dependent",
        status=MilestoneStatus.pending,
        depends_on=["m1"],
        steps_total=1,
        steps_completed=0,
    )
    steps = [
        Step(id="s1", goal_id="goal-1", milestone_id="m1", title="Root Step", completed=True),
        Step(id="s2", goal_id="goal-1", milestone_id="m2", title="Dependent Step", completed=False),
    ]
    service, repo = make_service([root, dependent], steps)

    updated = await service.update_milestone("goal-1", "m1", MilestoneStatus.done, "default")

    assert updated is not None
    assert updated.status == MilestoneStatus.done
    assert repo.goal.milestones_completed == 1
    assert next(milestone for milestone in repo.milestones if milestone.id == "m2").status == MilestoneStatus.active


@pytest.mark.asyncio
async def test_goal_level_steps_are_not_gated_by_milestones() -> None:
    milestone = Milestone(
        id="m1",
        goal_id="goal-1",
        node_id="M-01",
        title="Pending Milestone",
        status=MilestoneStatus.pending,
        depends_on=["mx"],
        steps_total=0,
        steps_completed=0,
    )
    goal_step = Step(id="s1", goal_id="goal-1", milestone_id=None, title="Global Step", completed=False)
    service, _ = make_service([milestone], [goal_step])

    updated = await service.update_step("goal-1", "s1", True, "default")

    assert updated is not None
    assert updated.completed is True


@pytest.mark.asyncio
async def test_submit_answers_updates_goal_summary_fields() -> None:
    service, repo = make_service([], [])
    repo.questions = [make_question()]

    result = await service.submit_answers(
        "goal-1",
        [AnswerItem(question_id="q1", answer="I have 10 hours per week")],
        "default",
    )

    assert result is not None
    assert repo.goal.synopsis == "Short summary"
    assert repo.goal.time_constraints == ["10 hours per week"]
    assert repo.goal.resources == ["Laptop"]
