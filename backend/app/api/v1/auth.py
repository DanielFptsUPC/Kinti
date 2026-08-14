from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.api.v1 import schemas
from app.core.config import get_settings
from app.core.security import TokenError, create_token, decode_token
from app.modules.identity import service as identity_service
from app.modules.patients import service as patients_service

router = APIRouter(tags=["identidad"])


def _issue_tokens(user_id: str, role: str) -> schemas.TokenPair:
    settings = get_settings()
    return schemas.TokenPair(
        access_token=create_token(user_id, "access", role),
        refresh_token=create_token(user_id, "refresh", role),
        expires_in=settings.access_token_minutes * 60,
    )


def _invalid_credentials() -> HTTPException:
    # Mensaje único y genérico: no revela si el correo existe.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_credentials", "message": "Correo o contraseña incorrectos"},
    )


@router.post("/auth/login", response_model=schemas.TokenPair)
async def login(body: schemas.LoginRequest, session: SessionDep) -> schemas.TokenPair:
    user = await identity_service.authenticate(session, body.email, body.password)
    if user is None:
        raise _invalid_credentials()
    if user.role == "patient":
        # Las cuentas del menor tienen su propia puerta (`/auth/patient-login`) y
        # un identificador interno que nadie le comunica. Rechazarlas aquí impide
        # que el alta infantil abra, de rebote, una entrada por el formulario
        # adulto. El mensaje es el genérico: no confirma que la cuenta exista.
        raise _invalid_credentials()
    return _issue_tokens(str(user.id), user.role)


@router.post("/auth/refresh", response_model=schemas.TokenPair)
async def refresh(body: schemas.RefreshRequest, session: SessionDep) -> schemas.TokenPair:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Sesión expirada"},
        ) from exc

    user = await identity_service.get_by_id(session, UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise _invalid_credentials()
    return _issue_tokens(str(user.id), user.role)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser) -> None:
    """Cierre de sesión del piloto.

    Los JWT son de vida corta y sin estado, así que el borrado efectivo ocurre
    en el cliente: elimina tokens de SecureStore y la caché local vinculada a la
    sesión. Este endpoint existe para que ese contrato quede explícito y para
    poder añadir una lista de revocación sin cambiar el cliente.
    """
    return None


@router.get("/me", response_model=schemas.MeResponse)
async def me(user: CurrentUser, session: SessionDep) -> schemas.MeResponse:
    patient_ids = await patients_service.authorized_patient_ids(session, user)
    return schemas.MeResponse(
        user=schemas.UserProfile(
            id=user.id, email=user.email, display_name=user.display_name, role=user.role
        ),
        patient_ids=patient_ids,
    )
