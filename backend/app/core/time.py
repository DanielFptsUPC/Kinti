from datetime import UTC, datetime
from zoneinfo import ZoneInfo

#: Todas las fechas se almacenan en UTC y se presentan en la zona del hospital.
DISPLAY_TIMEZONE = ZoneInfo("America/Lima")


def utcnow() -> datetime:
    """Instante actual, siempre timezone-aware en UTC."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normaliza a UTC. PostgreSQL puede devolver naive según el driver."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_display(value: datetime) -> datetime:
    """Convierte a `America/Lima` para presentación."""
    return as_utc(value).astimezone(DISPLAY_TIMEZONE)
