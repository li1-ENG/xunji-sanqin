import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import ADMIN_ACCOUNT, ADMIN_NAME, ADMIN_PASSWORD, SESSION_DAYS
from .models import AdminSession, AdminUser

PBKDF2_ITERATIONS = 260000

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False

def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def create_session(db: Session, user: AdminUser) -> str:
    token = secrets.token_urlsafe(40)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    db.add(AdminSession(token_hash=digest_token(token), user_id=user.id, expires_at=expires))
    db.commit()
    return token

def get_session_user(db: Session, token: str) -> AdminUser | None:
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == digest_token(token)))
    if not session:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    user = db.get(AdminUser, session.user_id)
    if not user or not user.is_active:
        return None
    return user

def revoke_session(db: Session, token: str) -> None:
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == digest_token(token)))
    if session:
        db.delete(session)
        db.commit()

def ensure_default_admin(db: Session) -> AdminUser:
    user = db.scalar(select(AdminUser).where(AdminUser.email == ADMIN_ACCOUNT.casefold()))
    if user:
        return user
    user = AdminUser(email=ADMIN_ACCOUNT.casefold(), display_name=ADMIN_NAME, password_hash=hash_password(ADMIN_PASSWORD))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
