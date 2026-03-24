from fastapi import APIRouter, Depends, HTTPException

from core.auth import UserIdDep
from dependencies import get_goals_service
from goals.models import (
    ClarifyingQuestion,
    CreateGoalRequest,
    CreateGoalResponse,
    Goal,
    Milestone,
    Plan,
    ReportBlockerRequest,
    Step,
    SubmitAnswersRequest,
    SubmitAnswersResponse,
    UpdateMilestoneRequest,
    UpdateStepRequest,
)
from goals.service import GoalsService

router = APIRouter()


@router.get("", response_model=list[Goal])
async def list_goals(
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> list[Goal]:
    return await service.list_goals(user_id)


@router.post("", response_model=CreateGoalResponse, status_code=201)
async def create_goal(
    body: CreateGoalRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> CreateGoalResponse:
    goal, questions = await service.create_goal(body.description, user_id)
    return CreateGoalResponse(goal=goal, questions=questions)


@router.get("/{goal_id}", response_model=Goal)
async def get_goal(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    goal = await service.get_goal(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.get("/{goal_id}/questions", response_model=list[ClarifyingQuestion])
async def get_questions(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> list[ClarifyingQuestion]:
    questions = await service.get_questions(goal_id, user_id)
    if questions is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return questions


@router.post("/{goal_id}/questions/answers", response_model=SubmitAnswersResponse)
async def submit_answers(
    goal_id: str,
    body: SubmitAnswersRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> SubmitAnswersResponse:
    result = await service.submit_answers(goal_id, body.answers, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
    return result


@router.post("/{goal_id}/plan/generate", response_model=Goal)
async def generate_plan(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    goal = await service.generate_plan(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.get("/{goal_id}/plan", response_model=Plan)
async def get_plan(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Plan:
    plan = await service.get_plan(goal_id, user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/{goal_id}/milestones/{milestone_id}", response_model=Milestone)
async def update_milestone(
    goal_id: str,
    milestone_id: str,
    body: UpdateMilestoneRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Milestone:
    milestone = await service.update_milestone(goal_id, milestone_id, body.status, user_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


@router.put("/{goal_id}/steps/{step_id}", response_model=Step)
async def update_step(
    goal_id: str,
    step_id: str,
    body: UpdateStepRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Step:
    step = await service.update_step(goal_id, step_id, body.completed, user_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


@router.post("/{goal_id}/blockers", response_model=Goal)
async def report_blocker(
    goal_id: str,
    body: ReportBlockerRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    goal = await service.report_blocker(goal_id, body.description, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.post("/{goal_id}/archive", response_model=Goal)
async def archive_goal(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    goal = await service.archive_goal(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal
