from aiodynamo.client import Client
from fastapi import Depends, Request

from app_config import app_config
from goals.ai import create_goals_ai
from goals.repository import GoalsRepository
from goals.service import GoalsService

_goals_ai = create_goals_ai()


def get_dynamo_client(request: Request) -> Client:
    return request.app.state.dynamo_client


def get_goals_repository(client: Client = Depends(get_dynamo_client)) -> GoalsRepository:
    return GoalsRepository(client=client, table_name=app_config.goals_table)


def get_goals_service(
    goals_repo: GoalsRepository = Depends(get_goals_repository),
) -> GoalsService:
    return GoalsService(goals_repo=goals_repo, goals_ai=_goals_ai)
