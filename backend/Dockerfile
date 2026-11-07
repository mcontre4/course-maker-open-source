FROM docker:28-cli AS docker-cli
FROM python:3.12-slim AS backend
WORKDIR /app
RUN pip install --no-cache-dir poetry==2.2.1
ENV POETRY_VIRTUALENVS_CREATE=false PYTHONUNBUFFERED=1
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --extras ai --no-root --no-interaction
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
ENV PYTHONPATH=/app/src
RUN useradd --create-home appuser \
    && mkdir -p /app/.artifacts/speech \
    && chown -R appuser:appuser /app/.artifacts
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Explicit local-only target. Production does not receive a Docker client/socket.
FROM backend AS animator-dev
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY scripts/check_animator_runtime.py ./check_animator_runtime.py

FROM backend AS production
