from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import DomainError, forbidden
from app.core.security import TokenError, decode_token
from app.modules.identity import service as identity_service
from app.modules.identity.models import User

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized", "message": "Sesión no válida"},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        raise _unauthorized() from exc

    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise _unauthorized() from exc

    user = await identity_service.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_caregiver(user: CurrentUser) -> User:
    if user.role != "caregiver":
        raise forbidden("Esta acción corresponde al cuidador vinculado").as_http()
    return user


async def require_care_team(user: CurrentUser) -> User:
    if user.role != "care_team":
        raise forbidden("Esta acción corresponde al equipo asistencial").as_http()
    return user


CaregiverUser = Annotated[User, Depends(require_caregiver)]
CareTeamUser = Annotated[User, Depends(require_care_team)]


def http_error(exc: DomainError) -> HTTPException:
    return exc.as_http()
