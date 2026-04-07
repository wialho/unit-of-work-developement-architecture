FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY apps/orchestrator ./apps/orchestrator
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/orchestrator/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
