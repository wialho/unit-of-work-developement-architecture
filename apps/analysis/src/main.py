from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from workflow_runtime import Database, Settings


settings = Settings.from_env("analysis")
db = Database(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    try:
        yield
    finally:
        await db.close()


app = FastAPI(title="workflow-analysis", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/analysis/summary")
async def summary() -> dict[str, str]:
    return {
        "status": "placeholder",
        "note": "Analysis reads durable workflow data and is intentionally outside the execution path.",
    }
