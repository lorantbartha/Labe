import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from goals.ai import GoalsAI
from goals.models import (
    AnswerItem,
    ClarifyingQuestion,
    Goal,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    Plan,
    Step,
    SubmitAnswersResponse,
)
from goals.repository import GoalsRepository


@dataclass(frozen=True)
class GoalsService:
    goals_repo: GoalsRepository
    goals_ai: GoalsAI

    async def list_goals(self, user_id: str) -> list[Goal]:
        return await self.goals_repo.list_goals(user_id)

    async def get_goal(self, goal_id: str, user_id: str) -> Goal | None:
        return await self.goals_repo.get_goal(goal_id, user_id)

    async def create_goal(self, description: str, user_id: str) -> tuple[Goal, list[ClarifyingQuestion]]:
        goal_id = str(uuid.uuid4())[:8]
        title, questions = await self.goals_ai.generate_questions(goal_id, description)
        goal = Goal(
            id=goal_id,
            user_id=user_id,
            title=title,
            description=description,
            status=GoalStatus.clarifying,
            milestones_total=0,
            milestones_completed=0,
            created_at=datetime.now(UTC).isoformat(),
        )
        await self.goals_repo.put_goal(goal, user_id)
        await self.goals_repo.put_questions(goal_id, questions, user_id)
        return goal, questions

    async def get_questions(self, goal_id: str, user_id: str) -> list[ClarifyingQuestion] | None:
        return await self.goals_repo.get_questions(goal_id, user_id)

    async def submit_answers(
        self, goal_id: str, answers: list[AnswerItem], user_id: str
    ) -> SubmitAnswersResponse | None:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if goal is None:
            return None
        questions = await self.goals_repo.get_questions(goal_id, user_id)
        if questions is None:
            return None

        answer_map = {a.question_id: a.answer for a in answers}
        updated_questions = [q.model_copy(update={"answer": answer_map.get(q.id, q.answer)}) for q in questions]
        await self.goals_repo.put_questions(goal_id, updated_questions, user_id)

        answered_qa = [(q.question, q.answer) for q in updated_questions if q.answer]
        current_round = max(q.round for q in updated_questions)
        has_enough, follow_ups, summary = await self.goals_ai.evaluate_sufficiency(
            goal_id=goal_id,
            description=goal.description,
            qa_pairs=answered_qa,
            next_question_index=len(updated_questions) + 1,
            current_round=current_round,
        )
        goal_summary_fields = {
            "synopsis": summary.synopsis,
            "time_constraints": summary.time_constraints,
            "resources": summary.resources,
            "current_state": summary.current_state,
            "success_criteria": summary.success_criteria,
            "risks_or_unknowns": summary.risks_or_unknowns,
        }
        goal = await self.goals_repo.update_goal_fields(goal_id, goal_summary_fields, user_id)

        if not has_enough and follow_ups:
            all_questions = updated_questions + follow_ups
            await self.goals_repo.put_questions(goal_id, all_questions, user_id)
            return SubmitAnswersResponse(status="needs_more_questions", questions=follow_ups)

        updated_goal = await self.goals_repo.update_goal_fields(
            goal_id,
            goal_summary_fields | {"status": GoalStatus.planning.value},
            user_id,
        )
        return SubmitAnswersResponse(status="ready", goal=updated_goal)

    async def generate_plan(self, goal_id: str, user_id: str) -> Goal | None:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            return None
        questions = await self.goals_repo.get_questions(goal_id, user_id) or []
        qa_pairs = [(q.question, q.answer or "") for q in questions if q.answer]
        milestones, steps = await self.goals_ai.generate_plan(goal_id, goal, qa_pairs)
        milestones = _recalculate_milestones(milestones, steps)
        await self.goals_repo.put_milestones_and_steps(goal_id, milestones, steps, user_id)
        return await self.goals_repo.update_goal_fields(
            goal_id,
            {"status": GoalStatus.active.value, "milestones_total": len(milestones)},
            user_id,
        )

    async def get_plan(self, goal_id: str, user_id: str) -> Plan | None:
        milestones = await self.goals_repo.get_milestones(goal_id, user_id)
        steps = await self.goals_repo.get_steps(goal_id, user_id)
        if milestones is None or steps is None:
            return None
        return Plan(goal_id=goal_id, milestones=milestones, steps=steps)

    async def update_milestone(
        self, goal_id: str, milestone_id: str, status: MilestoneStatus, user_id: str
    ) -> Milestone | None:
        milestones = await self.goals_repo.get_milestones(goal_id, user_id)
        if milestones is None:
            return None
        steps = await self.goals_repo.get_steps(goal_id, user_id) or []
        by_id = {m.id: m for m in milestones}
        found: Milestone | None = None
        for milestone in milestones:
            if milestone.id == milestone_id:
                found = milestone
                break
        if not found:
            return None

        if status == MilestoneStatus.done:
            if found.status != MilestoneStatus.active:
                raise ValueError("Only active milestones can be marked done")
            if not all(by_id[dep_id].status == MilestoneStatus.done for dep_id in found.depends_on if dep_id in by_id):
                raise ValueError("Milestone dependencies must be completed first")
            if any(not step.completed for step in steps if step.milestone_id == milestone_id):
                raise ValueError("All linked tasks must be completed before marking a milestone done")
        elif status == MilestoneStatus.active:
            raise ValueError("Milestone activation is automatic")

        updated = [
            milestone.model_copy(update={"status": status}) if milestone.id == milestone_id else milestone
            for milestone in milestones
        ]
        recalculated = _recalculate_milestones(updated, steps)
        await self.goals_repo.put_milestones_and_steps(goal_id, recalculated, steps, user_id)
        completed_count = sum(1 for milestone in recalculated if milestone.status == MilestoneStatus.done)
        await self.goals_repo.update_goal_fields(goal_id, {"milestones_completed": completed_count}, user_id)
        return next(milestone for milestone in recalculated if milestone.id == milestone_id)

    async def update_step(self, goal_id: str, step_id: str, completed: bool, user_id: str) -> Step | None:
        steps = await self.goals_repo.get_steps(goal_id, user_id)
        if steps is None:
            return None
        milestones = await self.goals_repo.get_milestones(goal_id, user_id) or []
        by_id = {m.id: m for m in milestones}
        found: Step | None = None
        updated: list[Step] = []
        for step in steps:
            if step.id == step_id:
                if step.milestone_id is not None:
                    milestone = by_id.get(step.milestone_id)
                    if milestone is None:
                        raise ValueError("Milestone for step was not found")
                    if milestone.status != MilestoneStatus.active:
                        raise ValueError("Tasks can only be completed for active milestones")
                found = step.model_copy(update={"completed": completed})
                updated.append(found)
            else:
                updated.append(step)
        if not found:
            return None
        recalculated = _recalculate_milestones(milestones, updated)
        await self.goals_repo.put_milestones_and_steps(goal_id, recalculated, updated, user_id)
        return found

    async def archive_goal(self, goal_id: str, user_id: str) -> Goal | None:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            return None
        return await self.goals_repo.update_goal_fields(goal_id, {"status": GoalStatus.archived.value}, user_id)

    async def report_blocker(self, goal_id: str, description: str, user_id: str) -> Goal | None:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            return None
        return await self.goals_repo.update_goal_fields(
            goal_id,
            {"status": GoalStatus.blocked.value, "blocker_reason": description},
            user_id,
        )


def _recalculate_milestones(milestones: list[Milestone], steps: list[Step]) -> list[Milestone]:
    step_counts: dict[str, tuple[int, int]] = {}
    for step in steps:
        if step.milestone_id is None:
            continue
        total, completed = step_counts.get(step.milestone_id, (0, 0))
        step_counts[step.milestone_id] = (total + 1, completed + int(step.completed))

    milestones_by_id = {milestone.id: milestone for milestone in milestones}
    recalculated = [
        milestone.model_copy(
            update={
                "steps_total": step_counts.get(milestone.id, (0, 0))[0],
                "steps_completed": step_counts.get(milestone.id, (0, 0))[1],
            }
        )
        for milestone in milestones
    ]

    final: list[Milestone] = []
    for milestone in recalculated:
        status = milestone.status
        if status != MilestoneStatus.done:
            deps_complete = all(
                milestones_by_id[dep_id].status == MilestoneStatus.done for dep_id in milestone.depends_on if dep_id in milestones_by_id
            )
            if status == MilestoneStatus.pending and deps_complete:
                status = MilestoneStatus.active
            elif status == MilestoneStatus.active and not deps_complete:
                status = MilestoneStatus.pending
        final.append(milestone.model_copy(update={"status": status}))

    return final
