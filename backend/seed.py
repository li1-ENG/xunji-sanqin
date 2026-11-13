from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal, init_db
from app.security import ensure_default_admin
from app.services.importer import import_processed

def main():
    init_db()
    db = SessionLocal()
    try:
        user = ensure_default_admin(db)
        print(f'admin: {user.email}')
        counts = import_processed(db)
        print('imported:', counts)
    finally:
        db.close()

if __name__ == '__main__':
    main()
