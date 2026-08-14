from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.modules.identity.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.strip().lower()))


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son válidas y la cuenta está activa.

    Verifica el hash incluso cuando el usuario no existe para no filtrar por
    tiempo de respuesta qué correos están registrados.
    """
    user = await get_by_email(session, email)
    if user is None:
        # Hash descartable con el mismo costo que una verificación real.
        verify_password(
            password,
            "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2E$"
            "0000000000000000000000000000000000000000000",
        )
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
