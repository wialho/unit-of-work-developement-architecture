FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/ticket-to-prompt ./apps/ticket-to-prompt
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/ticket-to-prompt/src
CMD ["python", "main.py"]
