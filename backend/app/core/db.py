from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def make_engine(url: str):
    return create_engine(
        url, pool_pre_ping=True, connect_args={"connect_timeout": 5} if url.startswith("postgresql") else {}
    )


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
analytics_engine = make_engine(settings.ANALYTICS_DATABASE_URL)


def get_db():
    with SessionLocal() as session:
        yield session
