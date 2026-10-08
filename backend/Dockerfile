FROM python:3.11-slim AS runtime
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
RUN useradd --create-home appuser
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.txt requirements-ml.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
USER appuser
CMD ["pytest", "-q"]

FROM runtime AS production

FROM runtime AS ml
USER root
COPY requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt
USER appuser
