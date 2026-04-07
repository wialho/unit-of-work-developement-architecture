FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/code-review ./apps/code-review
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/code-review/src
CMD ["python", "main.py"]
