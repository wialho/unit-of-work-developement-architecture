FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/failure-routing ./apps/failure-routing
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/failure-routing/src
CMD ["python", "main.py"]
