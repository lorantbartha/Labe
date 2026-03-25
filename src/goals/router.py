from fastapi import APIRouter, Depends

from core.auth import UserIdDep
from dependencies import get_goals_service
from goals.models import (
    AdaptPlanRequest,
    AdaptPlanResponse,
    ClarifyingQuestion,
    CreateGoalRequest,
    CreateGoalResponse,
    Goal,
    Milestone,
    Plan,
    Step,
    SubmitAnswersRequest,
    SubmitAnswersResponse,
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
    return await service.get_goal(goal_id, user_id)


@router.get("/{goal_id}/questions", response_model=list[ClarifyingQuestion])
async def get_questions(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> list[ClarifyingQuestion]:
    return await service.get_questions(goal_id, user_id)


@router.post("/{goal_id}/questions/answers", response_model=SubmitAnswersResponse)
async def submit_answers(
    goal_id: str,
    body: SubmitAnswersRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> SubmitAnswersResponse:
    return await service.submit_answers(goal_id, body.answers, user_id)


@router.post("/{goal_id}/plan/generate", response_model=Goal)
async def generate_plan(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    return await service.generate_plan(goal_id, user_id)


@router.get("/{goal_id}/plan", response_model=Plan)
async def get_plan(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Plan:
    return await service.get_plan(goal_id, user_id)


@router.post("/{goal_id}/milestones/{milestone_id}/finish", response_model=Milestone)
async def finish_milestone(
    goal_id: str,
    milestone_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Milestone:
    return await service.finish_milestone(goal_id, milestone_id, user_id)


@router.put("/{goal_id}/steps/{step_id}", response_model=Step)
async def update_step(
    goal_id: str,
    step_id: str,
    body: UpdateStepRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Step:
    return await service.update_step(goal_id, step_id, body.completed, user_id)


@router.post("/{goal_id}/plan/adapt", response_model=AdaptPlanResponse)
async def adapt_plan(
    goal_id: str,
    body: AdaptPlanRequest,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> AdaptPlanResponse:
    return await service.adapt_plan(goal_id, body.message, user_id)



@router.post("/{goal_id}/archive", response_model=Goal)
async def archive_goal(
    goal_id: str,
    user_id: UserIdDep,
    service: GoalsService = Depends(get_goals_service),
) -> Goal:
    return await service.archive_goal(goal_id, user_id)
