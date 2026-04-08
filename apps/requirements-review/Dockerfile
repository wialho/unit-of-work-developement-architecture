FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/requirements-review ./apps/requirements-review
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/requirements-review/src
CMD ["python", "main.py"]
