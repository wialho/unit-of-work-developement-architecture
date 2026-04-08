FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/test-runner ./apps/test-runner
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/test-runner/src
CMD ["python", "main.py"]
