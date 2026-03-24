from typing import Annotated

from fastapi import Depends, Header

DEFAULT_USER_ID = "default"


async def get_user_id(x_user_id: str | None = Header(None)) -> str:
    return x_user_id or DEFAULT_USER_ID


UserIdDep = Annotated[str, Depends(get_user_id)]
