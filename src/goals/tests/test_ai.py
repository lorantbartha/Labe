import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOALS_TABLE", "test-goals")

from pydantic_ai import Agent, RunContext

from goals.ai import (
    AdaptationContext,
    GoalsAI,
    GoalSummary,
    _MilestoneOutput,
    _PlanOutput,
    _QuestionOutput,
    _QuestionsResult,
    _StepOutput,
    _SufficiencyOutput,
    add_milestone,
    delete_milestone,
    edit_milestone,
    report_blocker,
    update_goal_fields,
)
from goals.models import Goal, GoalStatus, Milestone, MilestoneStatus, Step

# ── Helpers ────────────────────────────────────────────────────────────────────


def make_goals_ai() -> Any:
    return GoalsAI(
        clarifying_agent=MagicMock(spec=Agent),  # type: ignore[arg-type]
        sufficiency_agent=MagicMock(spec=Agent),  # type: ignore[arg-type]
        plan_agent=MagicMock(spec=Agent),  # type: ignore[arg-type]
        adaptation_agent=MagicMock(spec=Agent),  # type: ignore[arg-type]
    )


def mock_run(agent_mock: Any, output: object) -> None:
    result = MagicMock()
    result.output = output
    agent_mock.run = AsyncMock(return_value=result)


def make_goal(
    goal_id: str = "goal-1",
    title: str = "Test Goal",
    synopsis: str = "",
) -> Goal:
    return Goal(
        id=goal_id,
        user_id="default",
        title=title,
        description="Test description",
        synopsis=synopsis,
        status=GoalStatus.active,
        milestones_total=0,
        milestones_completed=0,
        created_at="2026-01-01T00:00:00+00:00",
    )


def make_milestone(
    id: str,
    node_id: str,
    title: str,
    goal_id: str = "goal-1",
    status: MilestoneStatus = MilestoneStatus.active,
    depends_on: list[str] | None = None,
) -> Milestone:
    return Milestone(
        id=id,
        goal_id=goal_id,
        node_id=node_id,
        title=title,
        status=status,
        depends_on=depends_on or [],
        steps_total=0,
        steps_completed=0,
    )


def make_step(id: str, milestone_id: str | None, title: str, goal_id: str = "goal-1") -> Step:
    return Step(id=id, goal_id=goal_id, milestone_id=milestone_id, title=title, completed=False)


def make_adaptation_context(
    milestones: list[Milestone],
    steps: list[Step],
    goal: Goal | None = None,
) -> AdaptationContext:
    node_id_to_milestone_id = {m.node_id: m.id for m in milestones}
    milestone_id_to_node_id = {m.id: m.node_id for m in milestones}
    return AdaptationContext(
        goal=goal or make_goal(),
        milestones=list(milestones),
        steps=list(steps),
        node_id_to_milestone_id=node_id_to_milestone_id,
        milestone_id_to_node_id=milestone_id_to_node_id,
    )


def make_ctx(context: AdaptationContext) -> Any:
    ctx = MagicMock(spec=RunContext)
    ctx.deps = context
    return ctx


# ── GoalsAI.generate_questions ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_questions_returns_title_and_questions() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.clarifying_agent,
        _QuestionsResult(
            title="Launch a SaaS MVP",
            questions=[
                _QuestionOutput(node_id="NODE_001", icon="schedule", question="What is your deadline?"),
                _QuestionOutput(node_id="NODE_002", icon="group", question="Solo or team?"),
            ],
        ),
    )

    title, questions = await ai.generate_questions("goal-1", "I want to launch a SaaS product")

    assert title == "Launch a SaaS MVP"
    assert len(questions) == 2
    assert questions[0].id == "goal-1_q1"
    assert questions[0].node_id == "NODE_001"
    assert questions[0].icon == "schedule"
    assert questions[0].question == "What is your deadline?"
    assert questions[0].round == 1
    assert questions[1].id == "goal-1_q2"


@pytest.mark.asyncio
async def test_generate_questions_prompt_includes_description() -> None:
    ai = make_goals_ai()
    mock_run(ai.clarifying_agent, _QuestionsResult(title="T", questions=[]))

    await ai.generate_questions("goal-1", "run a marathon")

    call_args = ai.clarifying_agent.run.call_args
    assert "run a marathon" in call_args[0][0]


@pytest.mark.asyncio
async def test_generate_questions_empty_returns_empty_list() -> None:
    ai = make_goals_ai()
    mock_run(ai.clarifying_agent, _QuestionsResult(title="Empty Goal", questions=[]))

    title, questions = await ai.generate_questions("goal-1", "something")

    assert title == "Empty Goal"
    assert questions == []


# ── GoalsAI.evaluate_sufficiency ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_evaluate_sufficiency_enough_info_returns_true_and_no_followups() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.sufficiency_agent,
        _SufficiencyOutput(
            has_enough_info=True,
            follow_up_questions=[],
            synopsis="User wants to run a marathon",
            time_constraints=["6 months"],
            resources=["Good trainers"],
            current_state=["Never run before"],
            success_criteria=["Finish under 4 hours"],
            risks_or_unknowns=["Injury risk"],
        ),
    )

    has_enough, follow_ups, summary = await ai.evaluate_sufficiency("goal-1", "run a marathon", [("Q?", "A!")], 2, 1)

    assert has_enough is True
    assert follow_ups == []
    assert isinstance(summary, GoalSummary)
    assert summary.synopsis == "User wants to run a marathon"
    assert summary.time_constraints == ["6 months"]
    assert summary.resources == ["Good trainers"]
    assert summary.current_state == ["Never run before"]
    assert summary.success_criteria == ["Finish under 4 hours"]
    assert summary.risks_or_unknowns == ["Injury risk"]


@pytest.mark.asyncio
async def test_evaluate_sufficiency_not_enough_returns_followups() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.sufficiency_agent,
        _SufficiencyOutput(
            has_enough_info=False,
            follow_up_questions=[
                _QuestionOutput(node_id="NODE_003", icon="flag", question="What is your target pace?"),
                _QuestionOutput(node_id="NODE_004", icon="schedule", question="How many days per week?"),
            ],
            synopsis="Training plan",
            time_constraints=[],
            resources=[],
            current_state=[],
            success_criteria=[],
            risks_or_unknowns=[],
        ),
    )

    has_enough, follow_ups, summary = await ai.evaluate_sufficiency(
        "goal-1", "run a marathon", [("Q?", "A!")], next_question_index=3, current_round=1
    )

    assert has_enough is False
    assert len(follow_ups) == 2
    assert follow_ups[0].id == "goal-1_q3"
    assert follow_ups[1].id == "goal-1_q4"
    assert follow_ups[0].round == 2  # current_round + 1
    assert follow_ups[1].round == 2


@pytest.mark.asyncio
async def test_evaluate_sufficiency_prompt_includes_qa_pairs() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.sufficiency_agent,
        _SufficiencyOutput(
            has_enough_info=True,
            follow_up_questions=[],
            synopsis="",
            time_constraints=[],
            resources=[],
            current_state=[],
            success_criteria=[],
            risks_or_unknowns=[],
        ),
    )

    await ai.evaluate_sufficiency("goal-1", "my goal", [("How long?", "6 months"), ("Solo?", "Yes")], 3, 1)

    prompt = ai.sufficiency_agent.run.call_args[0][0]
    assert "How long?" in prompt
    assert "6 months" in prompt
    assert "Solo?" in prompt
    assert "Total questions already asked: 2" in prompt


# ── GoalsAI.generate_plan ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_plan_creates_milestones_with_correct_statuses() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.plan_agent,
        _PlanOutput(
            milestones=[
                _MilestoneOutput(
                    node_id="M-01", title="Foundation Ready", description="Base set up", depends_on_node_ids=[]
                ),
                _MilestoneOutput(
                    node_id="M-02", title="Feature Built", description="Core built", depends_on_node_ids=["M-01"]
                ),
            ],
            steps=[
                _StepOutput(milestone_node_id="M-01", title="Set up project", order=1),
                _StepOutput(milestone_node_id="M-02", title="Build feature", order=1),
            ],
        ),
    )

    goal = make_goal()
    milestones, steps = await ai.generate_plan("goal-1", goal, [("Q?", "A!")])

    assert len(milestones) == 2
    m01 = next(m for m in milestones if m.node_id == "M-01")
    m02 = next(m for m in milestones if m.node_id == "M-02")

    assert m01.status == MilestoneStatus.active  # root: no deps
    assert m02.status == MilestoneStatus.pending  # has dep


@pytest.mark.asyncio
async def test_generate_plan_resolves_node_ids_to_real_ids() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.plan_agent,
        _PlanOutput(
            milestones=[
                _MilestoneOutput(node_id="M-01", title="Root", description="", depends_on_node_ids=[]),
                _MilestoneOutput(node_id="M-02", title="Child", description="", depends_on_node_ids=["M-01"]),
            ],
            steps=[],
        ),
    )

    milestones, _ = await ai.generate_plan("goal-1", make_goal(), [])

    m01 = next(m for m in milestones if m.node_id == "M-01")
    m02 = next(m for m in milestones if m.node_id == "M-02")

    assert m02.depends_on == [m01.id]  # real UUID, not "M-01"
    assert len(m01.id) == 8
    assert len(m02.id) == 8


@pytest.mark.asyncio
async def test_generate_plan_counts_steps_per_milestone() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.plan_agent,
        _PlanOutput(
            milestones=[
                _MilestoneOutput(node_id="M-01", title="Root", description="", depends_on_node_ids=[]),
            ],
            steps=[
                _StepOutput(milestone_node_id="M-01", title="Step 1", order=1),
                _StepOutput(milestone_node_id="M-01", title="Step 2", order=2),
                _StepOutput(milestone_node_id="M-01", title="Step 3", order=3),
            ],
        ),
    )

    milestones, steps = await ai.generate_plan("goal-1", make_goal(), [])

    assert milestones[0].steps_total == 3
    assert len(steps) == 3
    assert all(s.milestone_id == milestones[0].id for s in steps)


@pytest.mark.asyncio
async def test_generate_plan_goal_level_steps_have_no_milestone() -> None:
    ai = make_goals_ai()
    mock_run(
        ai.plan_agent,
        _PlanOutput(
            milestones=[
                _MilestoneOutput(node_id="M-01", title="Root", description="", depends_on_node_ids=[]),
            ],
            steps=[
                _StepOutput(milestone_node_id="M-01", title="Normal step", order=1),
                _StepOutput(milestone_node_id=None, title="Weekly review", order=1, recurring=True),
            ],
        ),
    )

    _, steps = await ai.generate_plan("goal-1", make_goal(), [])

    recurring = next(s for s in steps if s.recurring)
    assert recurring.milestone_id is None


# ── GoalsAI.adapt_plan ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adapt_plan_returns_five_tuple() -> None:
    ai = make_goals_ai()
    mock_run(ai.adaptation_agent, "Plan adapted successfully")

    m1 = make_milestone("m1", "M-01", "Root")
    goal = make_goal()
    result = await ai.adapt_plan(goal, [m1], [], "timeline moved up")

    assert len(result) == 5
    updated_goal, milestones, steps, change_log, summary = result
    assert updated_goal.id == "goal-1"
    assert milestones == [m1]
    assert steps == []
    assert change_log == []
    assert summary == "Plan adapted successfully"


@pytest.mark.asyncio
async def test_adapt_plan_prompt_includes_goal_and_milestones() -> None:
    ai = make_goals_ai()
    mock_run(ai.adaptation_agent, "done")

    m1 = make_milestone("m1", "M-01", "Foundation Ready")
    m2 = make_milestone("m2", "M-02", "Feature Built", depends_on=["m1"])
    goal = make_goal(title="Build a SaaS product")

    await ai.adapt_plan(goal, [m1, m2], [], "lost a team member")

    call_args = ai.adaptation_agent.run.call_args
    prompt = call_args[0][0]
    assert "Build a SaaS product" in prompt
    assert "M-01" in prompt
    assert "M-02" in prompt
    assert "lost a team member" in prompt


@pytest.mark.asyncio
async def test_adapt_plan_prompt_includes_change_history() -> None:
    ai = make_goals_ai()
    mock_run(ai.adaptation_agent, "done")

    await ai.adapt_plan(
        make_goal(),
        [],
        [],
        "new info",
        change_history=["[2026-01-01] Removed M-02: obsolete", "[2026-01-10] Added M-05: buffer time"],
    )

    prompt = ai.adaptation_agent.run.call_args[0][0]
    assert "Previous adaptations" in prompt
    assert "Removed M-02" in prompt
    assert "Added M-05" in prompt


@pytest.mark.asyncio
async def test_adapt_plan_prompt_no_history_section_when_empty() -> None:
    ai = make_goals_ai()
    mock_run(ai.adaptation_agent, "done")

    await ai.adapt_plan(make_goal(), [], [], "new info", change_history=None)

    prompt = ai.adaptation_agent.run.call_args[0][0]
    assert "Previous adaptations" not in prompt


# ── Tool: delete_milestone ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_milestone_removes_milestone_and_steps() -> None:
    m1 = make_milestone("m1", "M-01", "To Delete")
    m2 = make_milestone("m2", "M-02", "Keep This")
    s1 = make_step("s1", "m1", "Step for deleted")
    s2 = make_step("s2", "m2", "Step for kept")
    ctx = make_ctx(make_adaptation_context([m1, m2], [s1, s2]))

    result = await delete_milestone(ctx, "M-01", "no longer needed")

    assert "Deleted" in result
    assert not any(m.id == "m1" for m in ctx.deps.milestones)
    assert not any(s.id == "s1" for s in ctx.deps.steps)
    assert any(s.id == "s2" for s in ctx.deps.steps)
    assert len(ctx.deps.change_log) == 1
    assert "To Delete" in ctx.deps.change_log[0]


@pytest.mark.asyncio
async def test_delete_milestone_cleans_dependent_depends_on() -> None:
    m1 = make_milestone("m1", "M-01", "Parent")
    m2 = make_milestone("m2", "M-02", "Child", depends_on=["m1"])
    ctx = make_ctx(make_adaptation_context([m1, m2], []))

    await delete_milestone(ctx, "M-01", "removed")

    remaining = ctx.deps.milestones[0]
    assert remaining.id == "m2"
    assert "m1" not in remaining.depends_on


@pytest.mark.asyncio
async def test_delete_milestone_skips_done_milestone() -> None:
    m1 = make_milestone("m1", "M-01", "Done Work", status=MilestoneStatus.done)
    ctx = make_ctx(make_adaptation_context([m1], []))

    result = await delete_milestone(ctx, "M-01", "try to delete")

    assert "Skipped" in result
    assert len(ctx.deps.milestones) == 1
    assert len(ctx.deps.change_log) == 0


@pytest.mark.asyncio
async def test_delete_milestone_nonexistent_returns_error() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    result = await delete_milestone(ctx, "M-99", "delete nonexistent")

    assert "Error" in result
    assert len(ctx.deps.change_log) == 0


# ── Tool: add_milestone ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_milestone_creates_milestone_and_steps() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    result = await add_milestone(ctx, "M-01", "New Milestone", "Desc", [], ["Step 1", "Step 2"], "needed")

    assert "Added" in result
    assert len(ctx.deps.milestones) == 1
    m = ctx.deps.milestones[0]
    assert m.node_id == "M-01"
    assert m.title == "New Milestone"
    assert m.steps_total == 2
    assert len(ctx.deps.steps) == 2
    assert all(s.milestone_id == m.id for s in ctx.deps.steps)
    assert ctx.deps.steps[0].order == 1
    assert ctx.deps.steps[1].order == 2
    assert len(ctx.deps.change_log) == 1


@pytest.mark.asyncio
async def test_add_milestone_registers_in_lookup_maps() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    await add_milestone(ctx, "M-01", "New", "Desc", [], [], "reason")

    m = ctx.deps.milestones[0]
    assert ctx.deps.node_id_to_milestone_id["M-01"] == m.id
    assert ctx.deps.milestone_id_to_node_id[m.id] == "M-01"


@pytest.mark.asyncio
async def test_add_milestone_resolves_dependencies() -> None:
    existing = make_milestone("existing-id", "M-01", "Existing")
    ctx = make_ctx(make_adaptation_context([existing], []))

    await add_milestone(ctx, "M-02", "New", "Desc", ["M-01"], [], "dep on existing")

    new_m = next(m for m in ctx.deps.milestones if m.node_id == "M-02")
    assert new_m.depends_on == ["existing-id"]


@pytest.mark.asyncio
async def test_add_milestone_unknown_dep_node_ids_returns_error() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    result = await add_milestone(ctx, "M-01", "New", "Desc", ["M-99"], [], "bad dep")

    assert "Error" in result
    assert len(ctx.deps.milestones) == 0  # milestone not added


@pytest.mark.asyncio
async def test_add_milestone_duplicate_node_id_returns_error() -> None:
    existing = make_milestone("existing-id", "M-01", "Already Here")
    ctx = make_ctx(make_adaptation_context([existing], []))

    result = await add_milestone(ctx, "M-01", "Duplicate", "Desc", [], [], "try to add")

    assert "Error" in result
    assert len(ctx.deps.milestones) == 1  # no new milestone added


# ── Tool: edit_milestone ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_milestone_updates_title() -> None:
    m1 = make_milestone("m1", "M-01", "Old Title")
    ctx = make_ctx(make_adaptation_context([m1], []))

    result = await edit_milestone(ctx, "M-01", "scope changed", title="New Title")

    assert "Updated" in result
    assert ctx.deps.milestones[0].title == "New Title"
    assert ctx.deps.milestones[0].description == ""  # unchanged
    assert "title" in ctx.deps.change_log[0]


@pytest.mark.asyncio
async def test_edit_milestone_updates_description_only() -> None:
    m1 = make_milestone("m1", "M-01", "Keep Title")
    ctx = make_ctx(make_adaptation_context([m1], []))

    await edit_milestone(ctx, "M-01", "clarified", description="New description")

    assert ctx.deps.milestones[0].title == "Keep Title"
    assert ctx.deps.milestones[0].description == "New description"


@pytest.mark.asyncio
async def test_edit_milestone_updates_dependencies() -> None:
    m1 = make_milestone("m1", "M-01", "Root")
    m2 = make_milestone("m2", "M-02", "Target", depends_on=[])
    ctx = make_ctx(make_adaptation_context([m1, m2], []))

    await edit_milestone(ctx, "M-02", "added dep", depends_on_node_ids=["M-01"])

    assert ctx.deps.milestones[1].depends_on == ["m1"]  # resolved to real ID


@pytest.mark.asyncio
async def test_edit_milestone_nonexistent_returns_error() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    result = await edit_milestone(ctx, "M-99", "edit nonexistent", title="X")

    assert "Error" in result
    assert len(ctx.deps.change_log) == 0


@pytest.mark.asyncio
async def test_edit_milestone_no_fields_returns_no_changes() -> None:
    m1 = make_milestone("m1", "M-01", "Title")
    ctx = make_ctx(make_adaptation_context([m1], []))

    result = await edit_milestone(ctx, "M-01", "nothing to change")

    assert "No changes" in result
    assert len(ctx.deps.change_log) == 0


@pytest.mark.asyncio
async def test_edit_milestone_blocks_active_milestone() -> None:
    m1 = make_milestone("m1", "M-01", "Active Work", status=MilestoneStatus.active)
    ctx = make_ctx(make_adaptation_context([m1], []))

    result = await edit_milestone(ctx, "M-01", "external blocker appeared", status="blocked")

    assert "Updated" in result
    assert ctx.deps.milestones[0].status == MilestoneStatus.blocked
    assert "status" in ctx.deps.change_log[0]


@pytest.mark.asyncio
async def test_edit_milestone_unblocks_blocked_milestone() -> None:
    m1 = make_milestone("m1", "M-01", "Blocked Work", status=MilestoneStatus.blocked)
    ctx = make_ctx(make_adaptation_context([m1], []))

    await edit_milestone(ctx, "M-01", "blocker resolved", status="active")

    assert ctx.deps.milestones[0].status == MilestoneStatus.active


@pytest.mark.asyncio
async def test_edit_milestone_invalid_status_returns_error() -> None:
    m1 = make_milestone("m1", "M-01", "Work")
    ctx = make_ctx(make_adaptation_context([m1], []))

    result = await edit_milestone(ctx, "M-01", "try to complete", status="done")

    assert "Error" in result
    assert ctx.deps.milestones[0].status == MilestoneStatus.active  # unchanged
    assert len(ctx.deps.change_log) == 0


# ── Tool: update_goal_fields ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_goal_fields_updates_synopsis() -> None:
    goal = make_goal(synopsis="Old synopsis")
    ctx = make_ctx(make_adaptation_context([], [], goal=goal))

    result = await update_goal_fields(ctx, "context updated", synopsis="New synopsis")

    assert "Updated" in result
    assert ctx.deps.goal.synopsis == "New synopsis"
    assert len(ctx.deps.change_log) == 1
    assert "synopsis" in ctx.deps.change_log[0]


@pytest.mark.asyncio
async def test_update_goal_fields_updates_multiple_fields() -> None:
    goal = make_goal()
    ctx = make_ctx(make_adaptation_context([], [], goal=goal))

    await update_goal_fields(
        ctx,
        "timeline changed",
        time_constraints=["2 weeks"],
        success_criteria=["Ship MVP"],
    )

    assert ctx.deps.goal.time_constraints == ["2 weeks"]
    assert ctx.deps.goal.success_criteria == ["Ship MVP"]
    assert ctx.deps.goal.synopsis == ""  # unchanged


@pytest.mark.asyncio
async def test_update_goal_fields_no_fields_returns_no_changes() -> None:
    goal = make_goal()
    ctx = make_ctx(make_adaptation_context([], [], goal=goal))

    result = await update_goal_fields(ctx, "no fields")

    assert "No goal fields changed" in result
    assert len(ctx.deps.change_log) == 0


@pytest.mark.asyncio
async def test_update_goal_fields_does_not_touch_unchanged_fields() -> None:
    goal = make_goal()
    goal = goal.model_copy(update={"resources": ["Laptop"], "risks_or_unknowns": ["Unknown risk"]})
    ctx = make_ctx(make_adaptation_context([], [], goal=goal))

    await update_goal_fields(ctx, "only synopsis", synopsis="New synopsis")

    assert ctx.deps.goal.resources == ["Laptop"]
    assert ctx.deps.goal.risks_or_unknowns == ["Unknown risk"]


# ── report_blocker tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_report_blocker_sets_status_and_reason() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    result = await report_blocker(ctx, "Client approval pending", "waiting on external sign-off")

    assert "blocked" in result.lower()
    assert ctx.deps.goal.status == GoalStatus.blocked
    assert ctx.deps.goal.blocker_reason == "Client approval pending"
    assert any("Client approval pending" in e for e in ctx.deps.change_log)


@pytest.mark.asyncio
async def test_report_blocker_appends_to_change_log() -> None:
    ctx = make_ctx(make_adaptation_context([], []))

    await report_blocker(ctx, "Waiting for API keys", "third-party dependency")

    assert len(ctx.deps.change_log) == 1
    assert "Waiting for API keys" in ctx.deps.change_log[0]
