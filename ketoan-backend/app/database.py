"""
Kết nối Database dùng SQLAlchemy. Import `Base` này trong mọi model,
và `get_db` trong các API endpoint (qua Depends).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency dùng trong FastAPI endpoint: db: Session = Depends(get_db)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
