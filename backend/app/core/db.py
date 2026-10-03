from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
analytics_engine = create_engine(settings.ANALYTICS_DATABASE_URL, pool_pre_ping=True)


def get_db():
    with SessionLocal() as session:
        yield session
