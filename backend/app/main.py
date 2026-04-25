import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.examples import router as examples_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.query import router as query_router
from app.core.config import settings
from app.core.db import engine
from app.core.logging import setup_logging
from app.models import Base

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting application")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_origin_regex=settings.CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(examples_router)
app.include_router(history_router)
app.include_router(query_router)


@app.get("/")
def root():
    return {"message": "Analytics Query Assistant API is running"}