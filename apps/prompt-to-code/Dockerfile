FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY prompts ./prompts
COPY apps/prompt-to-code ./apps/prompt-to-code
RUN pip install --no-cache-dir -e .

WORKDIR /app/apps/prompt-to-code/src
CMD ["python", "main.py"]
