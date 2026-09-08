from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# HTTPBearer (rather than OAuth2PasswordBearer) makes Swagger's "Authorize" button
# just ask for a raw token to paste — OAuth2PasswordBearer instead renders a
# username/password form that POSTs form-encoded data to tokenUrl, which doesn't
# match this API's JSON-based /auth/login endpoint.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise AuthError("Not authenticated", code="not_authenticated")

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("Not authenticated", code="not_authenticated")
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise PermissionDeniedError("Admin access required", code="admin_required")
    return current_user
