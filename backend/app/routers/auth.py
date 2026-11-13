from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_admin, get_current_token
from ..models import AdminUser
from ..schemas import AdminOut, LoginRequest
from ..security import create_session, revoke_session, verify_password

router = APIRouter(prefix='/api/admin', tags=['admin-auth'])

@router.post('/auth/login')
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(AdminUser).where(AdminUser.email == payload.account.strip().casefold()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='邮箱或密码错误')
    token = create_session(db, user)
    return {'access_token': token, 'token_type': 'bearer', 'admin': AdminOut.model_validate(user).model_dump()}

@router.post('/auth/logout')
def logout(token: str = Depends(get_current_token), db: Session = Depends(get_db)):
    revoke_session(db, token)
    return {'message': '已退出登录'}

@router.get('/auth/me', response_model=AdminOut)
def me(user: AdminUser = Depends(get_current_admin)):
    return user
