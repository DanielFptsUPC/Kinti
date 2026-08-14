from fastapi import HTTPException, status


class DomainError(Exception):
    """Error de regla de negocio, con un código estable para el cliente."""

    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def as_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.http_status,
            detail={"code": self.code, "message": self.message},
        )


def not_found(message: str = "Recurso no encontrado") -> DomainError:
    """Se usa también para accesos no autorizados a recursos ajenos.

    Devolver 404 en vez de 403 evita que un UUID ajeno confirme la existencia
    de un paciente que el usuario no tiene permitido ver.
    """
    return DomainError("not_found", message, status.HTTP_404_NOT_FOUND)


def forbidden(message: str = "Acción no permitida para este rol") -> DomainError:
    return DomainError("forbidden", message, status.HTTP_403_FORBIDDEN)


def invalid(code: str, message: str) -> DomainError:
    # 422 literal: Starlette renombró la constante entre versiones.
    return DomainError(code, message, 422)
