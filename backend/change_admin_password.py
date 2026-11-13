from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ADMIN_ACCOUNT
from app.database import SessionLocal
from app.models import AdminSession, AdminUser
from app.security import hash_password
from sqlalchemy import delete, select


def main() -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(AdminUser).order_by(AdminUser.id))
        if not user:
            raise SystemExit('No admin account exists. Start the application once first.')
        password = getpass('New admin password: ')
        if len(password) < 10:
            raise SystemExit('Password must contain at least 10 characters.')
        if password != getpass('Confirm password: '):
            raise SystemExit('Passwords do not match.')
        user.password_hash = hash_password(password)
        db.execute(delete(AdminSession))
        db.commit()
        print(f'Password updated for: {user.email}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
