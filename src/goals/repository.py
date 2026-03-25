import json
import logging
from dataclasses import dataclass, field

from aiodynamo.client import Client, Table
from aiodynamo.expressions import F, HashKey
from aiodynamo.models import ReturnValues

from goals.models import ClarifyingQuestion, Goal, Milestone, Step

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoalsRepository:
    client: Client
    table_name: str
    _table: Table = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_table", self.client.table(self.table_name))

    async def list_goals(self, user_id: str) -> list[Goal]:
        items = []
        async for item in self._table.query(HashKey("user_id", user_id)):
            items.append(_item_to_goal(item))
        return items

    async def get_goal(self, goal_id: str, user_id: str) -> Goal | None:
        item = await self._table.get_item({"user_id": user_id, "id": goal_id})
        if item is None:
            return None
        return _item_to_goal(item)

    async def put_goal(self, goal: Goal, user_id: str) -> None:
        await self._table.put_item(_goal_to_item(goal, user_id))

    async def put_questions(self, goal_id: str, questions: list[ClarifyingQuestion], user_id: str) -> None:
        await self._table.update_item(
            key={"user_id": user_id, "id": goal_id},
            update_expression=F("questions").set(json.dumps([q.model_dump() for q in questions])),
            return_values=ReturnValues.none,
        )

    async def get_questions(self, goal_id: str, user_id: str) -> list[ClarifyingQuestion] | None:
        item = await self._table.get_item({"user_id": user_id, "id": goal_id})
        if item is None:
            return None
        raw = item.get("questions")
        if not raw:
            return []
        return [ClarifyingQuestion(**q) for q in json.loads(raw)]

    async def save_goal(self, goal: Goal, user_id: str) -> None:
        fields: dict = {
            "title": goal.title,
            "description": goal.description,
            "synopsis": goal.synopsis,
            "time_constraints": goal.time_constraints,
            "resources": goal.resources,
            "current_state": goal.current_state,
            "success_criteria": goal.success_criteria,
            "risks_or_unknowns": goal.risks_or_unknowns,
            "status": goal.status.value,
            "milestones_total": goal.milestones_total,
            "milestones_completed": goal.milestones_completed,
            "created_at": goal.created_at,
            "change_history": goal.change_history,
            "milestones": json.dumps([m.model_dump() for m in goal.milestones]),
            "steps": json.dumps([s.model_dump() for s in goal.steps]),
        }
        if goal.due_date is not None:
            fields["due_date"] = goal.due_date
        if goal.blocker_reason is not None:
            fields["blocker_reason"] = goal.blocker_reason

        items = iter(fields.items())
        key0, val0 = next(items)
        expr = F(key0).set(val0)
        for key, value in items:
            expr = expr & F(key).set(value)
        await self._table.update_item(
            key={"user_id": user_id, "id": goal.id},
            update_expression=expr,
            return_values=ReturnValues.none,
        )

    async def update_goal_fields(self, goal_id: str, fields: dict, user_id: str) -> Goal:
        items = iter(fields.items())
        key0, val0 = next(items)
        expr = F(key0).set(val0)
        for key, value in items:
            expr = expr & F(key).set(value)
        item = await self._table.update_item(
            key={"user_id": user_id, "id": goal_id},
            update_expression=expr,
            return_values=ReturnValues.all_new,
        )
        if item is None:
            raise RuntimeError(f"update_goal_fields returned no item for goal {goal_id}")
        return _item_to_goal(item)


def _goal_to_item(goal: Goal, user_id: str) -> dict:
    item: dict = {
        "user_id": user_id,
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "synopsis": goal.synopsis,
        "time_constraints": goal.time_constraints,
        "resources": goal.resources,
        "current_state": goal.current_state,
        "success_criteria": goal.success_criteria,
        "risks_or_unknowns": goal.risks_or_unknowns,
        "status": goal.status.value,
        "milestones_total": goal.milestones_total,
        "milestones_completed": goal.milestones_completed,
        "created_at": goal.created_at,
    }
    if goal.due_date is not None:
        item["due_date"] = goal.due_date
    if goal.blocker_reason is not None:
        item["blocker_reason"] = goal.blocker_reason
    return item


def _item_to_goal(item: dict) -> Goal:
    return Goal(
        id=item["id"],
        title=item["title"],
        description=item.get("description", ""),
        synopsis=item.get("synopsis", ""),
        time_constraints=list(item.get("time_constraints", [])),
        resources=list(item.get("resources", [])),
        current_state=list(item.get("current_state", [])),
        success_criteria=list(item.get("success_criteria", [])),
        risks_or_unknowns=list(item.get("risks_or_unknowns", [])),
        status=item["status"],
        milestones_total=int(item.get("milestones_total", 0)),
        milestones_completed=int(item.get("milestones_completed", 0)),
        due_date=item.get("due_date"),
        created_at=item["created_at"],
        blocker_reason=item.get("blocker_reason"),
        change_history=list(item.get("change_history", [])),
        milestones=[Milestone(**m) for m in json.loads(item["milestones"])] if item.get("milestones") else [],
        steps=[Step(**s) for s in json.loads(item["steps"])] if item.get("steps") else [],
    )
