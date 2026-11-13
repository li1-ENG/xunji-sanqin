from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import AdminUser
from .security import get_session_user

bearer = HTTPBearer(auto_error=False)

def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> AdminUser:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='需要管理员登录')
    user = get_session_user(db, credentials.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='登录已失效')
    return user

def get_current_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='需要管理员登录')
    return credentials.credentials
