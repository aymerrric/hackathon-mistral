"""SQLAlchemy engine / session setup. Fully implemented — nothing to do here.

Tables are created by db/schema.sql (mounted into the postgres container).
If you prefer ORM-driven creation, call Base.metadata.create_all(engine) at
startup instead — but keep schema.sql as the reference contract.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency yielding a request-scoped DB session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
