"""Kinti Compañero — endpoints del espacio del paciente.

La regla que gobierna este archivo: **ningún endpoint infantil acepta un
`patient_id` del cliente.** Siempre se deriva del token, que el servidor limita a
un único registro asistencial.

Tampoco se expone aquí nada del dominio operativo. La vista del menor se
construye por lista blanca en `companion/service.build_companion_view`.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CaregiverUser, CurrentUser, SessionDep
from app.api.v1 import schemas
from app.core.errors import DomainError, forbidden
from app.core.security import create_token, hash_password, verify_password
from app.modules.companion import service as companion
from app.modules.companion.models import PatientSupportRequest, PatientUserLink
from app.modules.identity.models import User

router = APIRouter(tags=["compañero"])


def _generic_login_error() -> HTTPException:
    # Mensaje único: no revela si el alias existe ni si la cuenta está suspendida.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_credentials",
            "message": "No pudimos entrar. Pide ayuda a tu adulto.",
        },
    )


@router.post("/auth/patient-login", response_model=schemas.TokenPair)
async def patient_login(
    body: schemas.PatientLoginRequest, session: SessionDep
) -> schemas.TokenPair:
    """Sesión restringida del menor.

    El token lleva `role=patient`; el servidor lo limita a su único paciente
    vinculado. **Nunca habilita Kinti Familia ni Kinti Equipo.**
    """
    from app.core.config import get_settings

    found = await companion.find_link_by_alias(session, body.alias)
    if found is None:
        raise _generic_login_error()

    account, link = found

    if companion.is_locked(link):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "code": "account_locked",
                "message": "Descansa un momento y vuelve a intentarlo con tu adulto.",
            },
        )

    if link.status != "active" or not account.is_active:
        raise _generic_login_error()

    if not verify_password(body.pin, account.password_hash):
        await companion.register_failed_attempt(session, link)
        await session.commit()
        raise _generic_login_error()

    await companion.register_successful_attempt(session, link)
    await session.commit()

    settings = get_settings()
    return schemas.TokenPair(
        access_token=create_token(str(account.id), "access", "patient"),
        refresh_token=create_token(str(account.id), "refresh", "patient"),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/patient/me/companion", response_model=schemas.CompanionViewOut)
async def companion_view(user: CurrentUser, session: SessionDep) -> schemas.CompanionViewOut:
    try:
        link = await companion.get_link_for_user(session, user)
        view = await companion.build_companion_view(session, link)
    except DomainError as exc:
        raise exc.as_http() from exc
    return schemas.CompanionViewOut.model_validate(view)


@router.post("/patient/me/feelings", response_model=schemas.FeelingOut)
async def record_own_feeling(
    body: schemas.RecordFeelingRequest, user: CurrentUser, session: SessionDep
) -> schemas.FeelingOut:
    """El menor registra cómo se siente. Una interacción, sin texto obligatorio.

    No genera alertas ni participa en ninguna priorización: acompaña.
    """
    from app.modules.care_routes import service as care_routes
    from app.modules.feelings import service as feelings_service

    try:
        link = await companion.get_link_for_user(session, user)
        feeling = await feelings_service.record_feeling(
            session,
            actor=user,
            patient_id=link.patient_id,
            mood=body.mood,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return schemas.FeelingOut.model_validate(care_routes.feeling_payload(feeling))


@router.post("/patient/me/support-requests", response_model=schemas.SupportRequestOut)
async def request_support(
    body: schemas.SupportRequestCreate, user: CurrentUser, session: SessionDep
) -> schemas.SupportRequestOut:
    """«Quiero hablar», «tengo miedo», «necesito ayuda», «quiero compañía».

    Llega al adulto responsable. El sistema no interpreta la causa.
    """
    try:
        link = await companion.get_link_for_user(session, user)
        request = await companion.create_support_request(
            session,
            account=user,
            link=link,
            request_type=body.request_type,
            operation_id=body.operation_id,
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _request_out(request)


@router.post(
    "/patient/me/preferences", response_model=schemas.CompanionViewOut
)
async def update_own_preferences(
    body: schemas.CompanionPreferencesRequest, user: CurrentUser, session: SessionDep
) -> schemas.CompanionViewOut:
    try:
        link = await companion.get_link_for_user(session, user)
        await companion.update_preferences(
            session,
            link=link,
            chosen_name=body.chosen_name,
            avatar_key=body.avatar_key,
            comfort_object=body.comfort_object,
        )
        view = await companion.build_companion_view(session, link)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return schemas.CompanionViewOut.model_validate(view)


# ------------------------------------------------- administración del adulto


@router.post(
    "/caregiver/patients/{patient_id}/patient-account",
    response_model=schemas.PatientAccountOut,
)
async def activate_patient_account(
    patient_id: UUID,
    body: schemas.PatientAccountRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.PatientAccountOut:
    """Alta de la cuenta infantil, con consentimiento explícito del apoderado."""
    if not body.consent_confirmed:
        raise forbidden("Se requiere el consentimiento del apoderado").as_http()

    try:
        account, link = await companion.activate_account(
            session,
            caregiver=user,
            patient_id=patient_id,
            alias=body.alias,
            pin_hash=hash_password(body.pin),
        )
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return await _account_out(session, account, link)


@router.patch(
    "/caregiver/patients/{patient_id}/patient-account",
    response_model=schemas.PatientAccountOut,
)
async def update_patient_account(
    patient_id: UUID,
    body: schemas.PatientAccountUpdateRequest,
    user: CaregiverUser,
    session: SessionDep,
) -> schemas.PatientAccountOut:
    """Recupera, suspende o configura el contenido habilitado.

    Suspender **no borra** el registro asistencial ni sus hitos.
    """
    from sqlalchemy import select

    try:
        await companion.require_caregiver_of(session, user, patient_id)

        link = await session.scalar(
            select(PatientUserLink).where(PatientUserLink.patient_id == patient_id)
        )
        if link is None:
            from app.core.errors import not_found

            raise not_found("Este paciente no tiene cuenta")

        if body.status is not None:
            link = await companion.set_account_status(
                session, caregiver=user, patient_id=patient_id, status=body.status
            )

        if body.pin is not None:
            # Recuperación por el adulto: el menor no restablece su propio acceso.
            account = await session.get(User, link.user_id)
            if account is not None:
                account.password_hash = hash_password(body.pin)
                link.failed_attempts = 0
                link.locked_until = None

        if body.development_band is not None or body.enabled_categories is not None:
            await companion.update_content_settings(
                session,
                caregiver=user,
                patient_id=patient_id,
                development_band=body.development_band,
                enabled_categories=body.enabled_categories,
            )

        account = await session.get(User, link.user_id)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return await _account_out(session, account, link)


@router.get(
    "/caregiver/patients/{patient_id}/support-requests",
    response_model=list[schemas.SupportRequestOut],
)
async def list_patient_support_requests(
    patient_id: UUID, user: CaregiverUser, session: SessionDep
) -> list[schemas.SupportRequestOut]:
    """El cuidador recibe las solicitudes, no cada interacción del menor."""
    try:
        await companion.require_caregiver_of(session, user, patient_id)
        requests = await companion.list_support_requests(session, patient_id)
    except DomainError as exc:
        raise exc.as_http() from exc
    return [_request_out(r) for r in requests]


@router.post(
    "/caregiver/support-requests/{request_id}/acknowledge",
    response_model=schemas.SupportRequestOut,
)
async def acknowledge_request(
    request_id: UUID, user: CaregiverUser, session: SessionDep
) -> schemas.SupportRequestOut:
    from app.core.errors import not_found

    request = await session.get(PatientSupportRequest, request_id)
    if request is None:
        raise not_found("Solicitud no encontrada").as_http()

    try:
        await companion.require_caregiver_of(session, user, request.patient_id)
        await companion.acknowledge_support_request(session, adult=user, request=request)
    except DomainError as exc:
        await session.rollback()
        raise exc.as_http() from exc

    await session.commit()
    return _request_out(request)


# ------------------------------------------------------------------ helpers


def _request_out(request: PatientSupportRequest) -> schemas.SupportRequestOut:
    return schemas.SupportRequestOut(
        id=request.id,
        patient_id=request.patient_id,
        request_type=request.request_type,
        status=request.status,
        created_at=request.created_at,
        acknowledged_at=request.acknowledged_at,
    )


async def _account_out(
    session, account: User | None, link: PatientUserLink
) -> schemas.PatientAccountOut:
    from sqlalchemy import select

    from app.modules.companion.models import PatientContentSettings

    settings = await session.scalar(
        select(PatientContentSettings).where(
            PatientContentSettings.patient_id == link.patient_id
        )
    )
    return schemas.PatientAccountOut(
        patient_id=link.patient_id,
        alias=account.display_name if account else "",
        status=link.status,
        development_band=settings.development_band if settings else "middle",
        enabled_categories=dict(
            (settings.enabled_categories if settings else None) or companion.DEFAULT_ENABLED
        ),
        consented_at=link.consented_at,
    )
