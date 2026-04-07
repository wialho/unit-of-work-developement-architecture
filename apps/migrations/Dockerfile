FROM postgres:16-alpine

WORKDIR /migrations
COPY migrations ./

CMD ["sh", "-c", "psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -f /migrations/001_init_workflow_schema.sql"]
