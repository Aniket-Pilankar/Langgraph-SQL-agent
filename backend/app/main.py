import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402

from agent.db import close_pools, get_admin_pool  # noqa: E402
from agent.graph import build_graph  # noqa: E402
from app.routes.chat import router as chat_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = AsyncPostgresSaver(await get_admin_pool())
    await checkpointer.setup()
    app.state.graph = build_graph(checkpointer=checkpointer)
    yield
    await close_pools()


app = FastAPI(title="LangGraph SQL Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(chat_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
