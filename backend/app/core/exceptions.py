from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message},
        )


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            "NOT_FOUND",
            f"{resource} not found",
            status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(
            "UNAUTHORIZED",
            message,
            status.HTTP_401_UNAUTHORIZED,
        )


class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(
            "CONFLICT",
            message,
            status.HTTP_409_CONFLICT,
        )
