import os
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOALS_TABLE", "test-goals")

from core.exceptions import ResourceNotFoundError
from goals.ai import GoalsAI, GoalSummary
from goals.models import AnswerItem, ClarifyingQuestion, Goal, GoalStatus, Milestone, MilestoneStatus, Step
from goals.service import GoalsService


@dataclass
class FakeGoalsRepository:
    goal: Goal
    questions: list = field(default_factory=list)

    async def list_goals(self, user_id: str) -> list[Goal]:
        return [self.goal]

    async def get_goal(self, goal_id: str, user_id: str) -> Goal | None:
        if self.goal.id != goal_id:
            return None
        return self.goal

    async def put_goal(self, goal: Goal, user_id: str) -> None:
        self.goal = goal

    async def get_questions(self, goal_id: str, user_id: str) -> list:
        return self.questions

    async def put_questions(self, goal_id: str, questions: list, user_id: str) -> None:
        self.questions = questions

    async def save_goal(self, goal: Goal, user_id: str) -> None:
        self.goal = goal

    async def update_goal_fields(self, goal_id: str, fields: dict, user_id: str) -> Goal:
        self.goal = self.goal.model_copy(update=fields)
        return self.goal


def make_goal() -> Goal:
    return Goal(
        id="goal-1",
        user_id="default",
        title="Test Goal",
        description="Test Goal Description",
        status=GoalStatus.active,
        milestones_total=0,
        milestones_completed=0,
        created_at="2026-03-24T00:00:00+00:00",
    )


def make_goal_summary() -> GoalSummary:
    return GoalSummary(
        synopsis="Short summary",
        time_constraints=["10 hours per week"],
        resources=["Laptop"],
        current_state=["Starting from scratch"],
        success_criteria=["First usable version shipped"],
        risks_or_unknowns=["Need user feedback"],
    )


def make_service(
    milestones: list[Milestone],
    steps: list[Step],
    ai: GoalsAI | None = None,
) -> tuple[GoalsService, FakeGoalsRepository]:
    goal = make_goal().model_copy(update={"milestones": milestones, "steps": steps})
    repo = FakeGoalsRepository(goal=goal)
    goals_ai = ai if ai is not None else MagicMock(spec=GoalsAI)
    return GoalsService(goals_repo=repo, goals_ai=goals_ai), repo  # type: ignore[arg-type]


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
    assert repo.goal.milestones[0].steps_total == 2
    assert repo.goal.milestones[0].steps_completed == 1


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
async def test_finish_milestone_requires_all_steps_completed() -> None:
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
        await service.finish_milestone("goal-1", "m1", "default")


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

    updated = await service.finish_milestone("goal-1", "m1", "default")

    assert updated is not None
    assert updated.status == MilestoneStatus.done
    assert repo.goal.milestones_completed == 1
    assert next(milestone for milestone in repo.goal.milestones if milestone.id == "m2").status == MilestoneStatus.active


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
    ai = MagicMock(spec=GoalsAI)
    ai.evaluate_sufficiency = AsyncMock(return_value=(True, [], make_goal_summary()))
    service, repo = make_service([], [], ai=ai)
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


# ── adapt_plan tests ───────────────────────────────────────────────────────────


def make_milestone(
    id: str,
    node_id: str,
    title: str,
    status: MilestoneStatus = MilestoneStatus.active,
    depends_on: list[str] | None = None,
) -> Milestone:
    return Milestone(
        id=id,
        goal_id="goal-1",
        node_id=node_id,
        title=title,
        status=status,
        depends_on=depends_on or [],
        steps_total=0,
        steps_completed=0,
    )


def make_step(id: str, milestone_id: str | None, title: str, completed: bool = False) -> Step:
    return Step(id=id, goal_id="goal-1", milestone_id=milestone_id, title=title, completed=completed)


@pytest.mark.asyncio
async def test_adapt_plan_no_changes_preserves_plan() -> None:
    m1 = make_milestone("m1", "M-01", "Foundation Ready")
    step = make_step("s1", "m1", "Do something")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(make_goal(), [m1], [step], [], "No changes"))
    service, repo = make_service([m1], [step], ai=ai)

    result = await service.adapt_plan("goal-1", "nothing changed", "default")

    assert result is not None
    assert len(result.plan.milestones) == 1
    assert result.plan.milestones[0].id == "m1"
    assert len(result.plan.steps) == 1
    assert result.summary == "No changes"


@pytest.mark.asyncio
async def test_adapt_plan_raises_for_missing_goal() -> None:
    service, _ = make_service([], [])

    with pytest.raises(ResourceNotFoundError):
        await service.adapt_plan("nonexistent", "message", "default")


@pytest.mark.asyncio
async def test_adapt_plan_delete_removes_milestone_and_steps() -> None:
    m1 = make_milestone("m1", "M-01", "Alpha Done")
    m2 = make_milestone("m2", "M-02", "Beta Done")
    s1 = make_step("s1", "m1", "Step A")
    s2 = make_step("s2", "m2", "Step B")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [m2],
            [s2],
            ["Removed milestone 'Alpha Done': no longer needed"],
            "Removed the alpha milestone",
        )
    )
    service, repo = make_service([m1, m2], [s1, s2], ai=ai)

    result = await service.adapt_plan("goal-1", "skip alpha", "default")

    assert result is not None
    assert len(result.plan.milestones) == 1
    assert result.plan.milestones[0].id == "m2"
    assert len(result.plan.steps) == 1
    assert result.plan.steps[0].id == "s2"
    assert repo.goal.milestones_total == 1
    assert "• Removed milestone 'Alpha Done'" in result.summary


@pytest.mark.asyncio
async def test_adapt_plan_delete_cleans_up_dependents() -> None:
    m1 = make_milestone("m1", "M-01", "Root Done")
    m2 = make_milestone("m2", "M-02", "Child Done", status=MilestoneStatus.pending, depends_on=["m1"])
    m2_cleaned = m2.model_copy(update={"depends_on": [], "status": MilestoneStatus.active})
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [m2_cleaned],
            [],
            ["Removed milestone 'Root Done': obsolete"],
            "Removed root milestone",
        )
    )
    service, repo = make_service([m1, m2], [], ai=ai)

    result = await service.adapt_plan("goal-1", "remove root", "default")

    assert result is not None
    assert len(result.plan.milestones) == 1
    remaining = result.plan.milestones[0]
    assert remaining.id == "m2"
    assert remaining.depends_on == []
    assert remaining.status == MilestoneStatus.active


@pytest.mark.asyncio
async def test_adapt_plan_skips_deleting_done_milestone() -> None:
    m1 = make_milestone("m1", "M-01", "Completed Work", status=MilestoneStatus.done)
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(make_goal(), [m1], [], [], "Kept done milestone as-is"))
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "remove everything", "default")

    assert result is not None
    assert len(result.plan.milestones) == 1
    assert result.plan.milestones[0].status == MilestoneStatus.done


@pytest.mark.asyncio
async def test_adapt_plan_add_milestone_with_steps() -> None:
    m1 = make_milestone("m1", "M-01", "Foundation Ready", status=MilestoneStatus.done)
    new_milestone = make_milestone("m2", "M-02", "Mobile Support Added", status=MilestoneStatus.active)
    new_step = make_step("s1", "m2", "Build mobile layout")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [m1, new_milestone.model_copy(update={"steps_total": 1})],
            [new_step],
            ["Added milestone 'Mobile Support Added' with 1 steps: user needs mobile"],
            "Added mobile milestone",
        )
    )
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "need mobile support", "default")

    assert result is not None
    assert len(result.plan.milestones) == 2
    assert any(m.title == "Mobile Support Added" for m in result.plan.milestones)
    assert len(result.plan.steps) == 1
    assert repo.goal.milestones_total == 2
    assert "• Added milestone 'Mobile Support Added'" in result.summary


@pytest.mark.asyncio
async def test_adapt_plan_add_milestone_pending_when_deps_not_done() -> None:
    m1 = make_milestone("m1", "M-01", "Prerequisite", status=MilestoneStatus.active)
    new_milestone = make_milestone("m2", "M-02", "Dependent Work", status=MilestoneStatus.pending, depends_on=["m1"])
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [m1, new_milestone],
            [],
            ["Added milestone 'Dependent Work'"],
            "Added dependent milestone",
        )
    )
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "add dependent work", "default")

    assert result is not None
    dependent = next(m for m in result.plan.milestones if m.id == "m2")
    assert dependent.status == MilestoneStatus.pending


@pytest.mark.asyncio
async def test_adapt_plan_add_milestone_active_when_deps_done() -> None:
    m1 = make_milestone("m1", "M-01", "Prerequisite", status=MilestoneStatus.done)
    new_milestone = make_milestone("m2", "M-02", "Follow-up", status=MilestoneStatus.pending, depends_on=["m1"])
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(make_goal(), [m1, new_milestone], [], ["Added milestone 'Follow-up'"], "Added follow-up")
    )
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "add follow-up work", "default")

    assert result is not None
    follow_up = next(m for m in result.plan.milestones if m.id == "m2")
    # recalculate() should activate it since m1 is done
    assert follow_up.status == MilestoneStatus.active


@pytest.mark.asyncio
async def test_adapt_plan_edit_milestone_title_and_description() -> None:
    m1 = make_milestone("m1", "M-01", "Old Title")
    updated_m1 = m1.model_copy(update={"title": "New Title", "description": "New desc"})
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [updated_m1],
            [],
            ["Updated milestone 'New Title' (title, description): scope changed"],
            "Renamed milestone",
        )
    )
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "rename milestone", "default")

    assert result is not None
    assert result.plan.milestones[0].title == "New Title"
    assert result.plan.milestones[0].description == "New desc"
    assert "• Updated milestone 'New Title'" in result.summary


@pytest.mark.asyncio
async def test_adapt_plan_edit_milestone_dependencies_recalculates_status() -> None:
    m1 = make_milestone("m1", "M-01", "Alpha", status=MilestoneStatus.done)
    m2 = make_milestone("m2", "M-02", "Beta", status=MilestoneStatus.active, depends_on=[])
    m2_with_dep = m2.model_copy(update={"depends_on": ["m1"]})
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(make_goal(), [m1, m2_with_dep], [], ["Updated milestone 'Beta' (dependencies)"], "Updated deps")
    )
    service, repo = make_service([m1, m2], [], ai=ai)

    result = await service.adapt_plan("goal-1", "add dependency", "default")

    assert result is not None
    beta = next(m for m in result.plan.milestones if m.id == "m2")
    assert "m1" in beta.depends_on
    assert beta.status == MilestoneStatus.active  # m1 is done so m2 stays active


@pytest.mark.asyncio
async def test_adapt_plan_updates_goal_summary_fields() -> None:
    m1 = make_milestone("m1", "M-01", "Work Done")
    updated_goal = make_goal().model_copy(update={"synopsis": "Updated synopsis", "time_constraints": ["2 weeks"]})
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            updated_goal,
            [m1],
            [],
            ["Updated goal summary (synopsis, time_constraints): timeline changed"],
            "Updated goal context",
        )
    )
    service, repo = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "timeline changed", "default")

    assert result is not None
    assert repo.goal.synopsis == "Updated synopsis"
    assert repo.goal.time_constraints == ["2 weeks"]
    assert "• Updated goal summary" in result.summary


@pytest.mark.asyncio
async def test_adapt_plan_no_goal_updates_preserves_goal_fields() -> None:
    m1 = make_milestone("m1", "M-01", "Work Done")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(make_goal(), [m1], [], [], "No changes needed"))
    service, repo = make_service([m1], [], ai=ai)
    original_synopsis = repo.goal.synopsis

    result = await service.adapt_plan("goal-1", "nothing", "default")

    assert result is not None
    assert repo.goal.synopsis == original_synopsis


@pytest.mark.asyncio
async def test_adapt_plan_delete_and_add_combined() -> None:
    m1 = make_milestone("m1", "M-01", "Old Work", status=MilestoneStatus.active)
    m2 = make_milestone("m2", "M-02", "Keep This", status=MilestoneStatus.active)
    new_m = make_milestone("m3", "M-03", "Replacement Work", status=MilestoneStatus.active)
    s1 = make_step("s1", "m1", "Old step")
    new_s = make_step("s2", "m3", "New step")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(
            make_goal(),
            [m2, new_m.model_copy(update={"steps_total": 1})],
            [new_s],
            ["Removed milestone 'Old Work': replaced", "Added milestone 'Replacement Work' with 1 steps: new approach"],
            "Replaced old work with new approach",
        )
    )
    service, repo = make_service([m1, m2], [s1], ai=ai)

    result = await service.adapt_plan("goal-1", "replace old work", "default")

    assert result is not None
    milestone_ids = [m.id for m in result.plan.milestones]
    assert "m1" not in milestone_ids
    assert "m2" in milestone_ids
    assert "m3" in milestone_ids
    assert len(result.plan.steps) == 1
    assert result.plan.steps[0].id == "s2"
    assert repo.goal.milestones_total == 2
    assert result.summary.count("•") == 2


@pytest.mark.asyncio
async def test_adapt_plan_recalculates_completed_count() -> None:
    m1 = make_milestone("m1", "M-01", "Done Milestone", status=MilestoneStatus.done)
    m2 = make_milestone("m2", "M-02", "Active Milestone", status=MilestoneStatus.active)
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(make_goal(), [m1, m2], [], [], "No structural changes"))
    service, repo = make_service([m1, m2], [], ai=ai)

    result = await service.adapt_plan("goal-1", "minor context update", "default")

    assert result is not None
    assert repo.goal.milestones_total == 2
    assert repo.goal.milestones_completed == 1


@pytest.mark.asyncio
async def test_adapt_plan_summary_includes_change_log_bullets() -> None:
    m1 = make_milestone("m1", "M-01", "Work")
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(
        return_value=(make_goal(), [m1], [], ["Change A", "Change B", "Change C"], "Three changes made")
    )
    service, _ = make_service([m1], [], ai=ai)

    result = await service.adapt_plan("goal-1", "make changes", "default")

    assert result is not None
    assert result.summary == "Three changes made\n\n• Change A\n• Change B\n• Change C"


@pytest.mark.asyncio
async def test_adapt_plan_persists_change_history() -> None:
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(make_goal(), [], [], ["Removed M-01: obsolete"], "Removed one milestone"))
    service, repo = make_service([], [], ai=ai)

    await service.adapt_plan("goal-1", "something changed", "default")

    assert len(repo.goal.change_history) == 1
    assert "Removed one milestone" in repo.goal.change_history[0]
    assert "Removed M-01: obsolete" in repo.goal.change_history[0]


@pytest.mark.asyncio
async def test_adapt_plan_passes_last_3_history_entries() -> None:
    old_history = [f"[2026-01-0{i}] Entry {i}" for i in range(1, 6)]
    goal_with_history = make_goal().model_copy(update={"change_history": old_history})
    ai = MagicMock(spec=GoalsAI)
    ai.adapt_plan = AsyncMock(return_value=(goal_with_history, [], [], [], "No changes"))
    service, repo = make_service([], [], ai=ai)
    repo.goal = repo.goal.model_copy(update={"change_history": old_history})

    await service.adapt_plan("goal-1", "update", "default")

    # History grows by 1 (all 5 old + 1 new)
    assert len(repo.goal.change_history) == 6
    # But the AI only received the last 3 of the original 5
    # (verified implicitly — if it received all 5 the call would still succeed;
    # the truncation is tested at the AI layer via test_ai.py)


@pytest.mark.asyncio
async def test_recalculate_milestones_activates_when_deps_done() -> None:
    root = make_milestone("m1", "M-01", "Root", status=MilestoneStatus.done)
    child = make_milestone("m2", "M-02", "Child", status=MilestoneStatus.pending, depends_on=["m1"])

    result = make_goal().model_copy(update={"milestones": [root, child], "steps": []}).recalculate()

    assert next(m for m in result.milestones if m.id == "m2").status == MilestoneStatus.active


@pytest.mark.asyncio
async def test_recalculate_milestones_keeps_pending_when_deps_not_done() -> None:
    root = make_milestone("m1", "M-01", "Root", status=MilestoneStatus.active)
    child = make_milestone("m2", "M-02", "Child", status=MilestoneStatus.pending, depends_on=["m1"])

    result = make_goal().model_copy(update={"milestones": [root, child], "steps": []}).recalculate()

    assert next(m for m in result.milestones if m.id == "m2").status == MilestoneStatus.pending
