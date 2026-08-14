from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.common import TimestampMixin, UuidPkMixin


class User(UuidPkMixin, TimestampMixin, Base):
    """Cuenta sintética del piloto.

    El niño no tiene credenciales propias: entra a su experiencia desde la
    sesión del cuidador vinculado.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
