"""管理者 Bearer トークン認証"""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tas.config import settings

_bearer = HTTPBearer()


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if not hmac.compare_digest(credentials.credentials, settings.admin_secret_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )
