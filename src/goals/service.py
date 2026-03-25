import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from core.exceptions import ResourceNotFoundError
from goals.ai import GoalsAI
from goals.models import (
    AdaptPlanResponse,
    AnswerItem,
    ClarifyingQuestion,
    Goal,
    GoalStatus,
    Milestone,
    Plan,
    Step,
    SubmitAnswersResponse,
)
from goals.repository import GoalsRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoalsService:
    goals_repo: GoalsRepository
    goals_ai: GoalsAI

    async def list_goals(self, user_id: str) -> list[Goal]:
        goals = await self.goals_repo.list_goals(user_id)
        logger.info("Listed %d goals for user %s", len(goals), user_id)
        return goals

    async def get_goal(self, goal_id: str, user_id: str) -> Goal:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Goal not found")
        return goal

    async def create_goal(self, description: str, user_id: str) -> tuple[Goal, list[ClarifyingQuestion]]:
        goal_id = str(uuid.uuid4())[:8]
        logger.info("Creating goal %s for user %s", goal_id, user_id)
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
        logger.info("Created goal %s with %d questions", goal_id, len(questions))
        return goal, questions

    async def get_questions(self, goal_id: str, user_id: str) -> list[ClarifyingQuestion]:
        questions = await self.goals_repo.get_questions(goal_id, user_id)
        if questions is None:
            raise ResourceNotFoundError("Goal not found")
        return questions

    async def submit_answers(self, goal_id: str, answers: list[AnswerItem], user_id: str) -> SubmitAnswersResponse:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if goal is None:
            raise ResourceNotFoundError("Goal not found")
        questions = await self.goals_repo.get_questions(goal_id, user_id)
        if questions is None:
            raise ResourceNotFoundError("Goal not found")

        answer_map = {a.question_id: a.answer for a in answers}
        updated_questions = [q.model_copy(update={"answer": answer_map.get(q.id, q.answer)}) for q in questions]
        await self.goals_repo.put_questions(goal_id, updated_questions, user_id)

        answered_qa = [(q.question, q.answer) for q in updated_questions if q.answer]
        current_round = max((q.round for q in updated_questions), default=1)
        logger.info(
            "Evaluating sufficiency for goal %s, round %d, %d answered", goal_id, current_round, len(answered_qa)
        )
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

        if not has_enough and follow_ups:
            await self.goals_repo.update_goal_fields(goal_id, goal_summary_fields, user_id)
            all_questions = updated_questions + follow_ups
            await self.goals_repo.put_questions(goal_id, all_questions, user_id)
            return SubmitAnswersResponse(status="needs_more_questions", questions=follow_ups)

        updated_goal = await self.goals_repo.update_goal_fields(
            goal_id,
            goal_summary_fields | {"status": GoalStatus.planning.value},
            user_id,
        )
        return SubmitAnswersResponse(status="ready", goal=updated_goal)

    async def generate_plan(self, goal_id: str, user_id: str) -> Goal:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Goal not found")
        logger.info("Generating plan for goal %s", goal_id)
        questions = await self.goals_repo.get_questions(goal_id, user_id) or []
        qa_pairs = [(q.question, q.answer or "") for q in questions if q.answer]
        milestones, steps = await self.goals_ai.generate_plan(goal_id, goal, qa_pairs)
        updated = goal.model_copy(
            update={"milestones": milestones, "steps": steps, "status": GoalStatus.active}
        ).recalculate()
        await self.goals_repo.save_goal(updated, user_id)
        logger.info(
            "Generated plan for goal %s: %d milestones, %d steps", goal_id, len(updated.milestones), len(updated.steps)
        )
        return updated

    async def get_plan(self, goal_id: str, user_id: str) -> Plan:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Plan not found")
        return Plan(goal_id=goal_id, milestones=goal.milestones, steps=goal.steps)

    async def finish_milestone(self, goal_id: str, milestone_id: str, user_id: str) -> Milestone:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Milestone not found")
        logger.info("Finishing milestone %s in goal %s", milestone_id, goal_id)
        updated, milestone = goal.finish_milestone(milestone_id)  # raises ValueError on invalid
        await self.goals_repo.save_goal(updated, user_id)
        return milestone

    async def update_step(self, goal_id: str, step_id: str, completed: bool, user_id: str) -> Step:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Step not found")
        if not goal.step_by_id(step_id):
            raise ResourceNotFoundError("Step not found")
        updated, step = goal.update_step(step_id, completed)  # raises ValueError on invalid
        await self.goals_repo.save_goal(updated, user_id)
        return step

    async def archive_goal(self, goal_id: str, user_id: str) -> Goal:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Goal not found")
        return await self.goals_repo.update_goal_fields(goal_id, {"status": GoalStatus.archived.value}, user_id)

    async def adapt_plan(self, goal_id: str, user_message: str, user_id: str) -> AdaptPlanResponse:
        goal = await self.goals_repo.get_goal(goal_id, user_id)
        if not goal:
            raise ResourceNotFoundError("Goal not found")
        logger.info(
            "Adapting plan for goal %s: %d milestones, %d steps", goal_id, len(goal.milestones), len(goal.steps)
        )
        returned_goal, milestones, steps, change_log, agent_summary = await self.goals_ai.adapt_plan(
            goal, goal.milestones, goal.steps, user_message, goal.recent_change_history()
        )

        logger.info("Adapted plan for goal %s: %d changes", goal_id, len(change_log))
        if change_log:
            summary = agent_summary + "\n\n" + "\n".join(f"• {entry}" for entry in change_log)
        else:
            summary = agent_summary

        updated = goal.model_copy(update={
            **returned_goal.summary_fields(),
            "milestones": milestones,
            "steps": steps,
            "change_history": goal.add_change_entry(summary),
        }).recalculate()
        await self.goals_repo.save_goal(updated, user_id)

        return AdaptPlanResponse(
            plan=Plan(goal_id=goal_id, milestones=updated.milestones, steps=updated.steps), summary=summary
        )

