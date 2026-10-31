class AppException(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    status_code = 404
    code = "not_found"


class ValidationError(AppException):
    status_code = 422
    code = "validation_error"


class DuplicateResourceError(AppException):
    status_code = 409
    code = "duplicate_resource"


class AuthError(AppException):
    status_code = 401
    code = "auth_error"


class PermissionDeniedError(AppException):
    status_code = 403
    code = "permission_denied"


class AIServiceError(AppException):
    status_code = 502
    code = "ai_service_error"


class AIServiceUnavailableError(AIServiceError):
    status_code = 503
    code = "ai_service_unavailable"


class AIServiceConfigError(AIServiceError):
    status_code = 500
    code = "ai_service_config_error"


class AIResponseInvalidError(AIServiceError):
    status_code = 502
    code = "ai_response_invalid"


class StorageError(AppException):
    """The photo store (e.g. S3) failed: bad credentials, missing bucket, network."""

    status_code = 502
    code = "storage_error"
