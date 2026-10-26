
from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "APPLICATION_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
        },
    )
