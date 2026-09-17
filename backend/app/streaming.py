import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from agent.graph import RECURSION_LIMIT
from app.sse import sse

logger = logging.getLogger(__name__)

PROGRESS_LABELS = {
    "retrieve_schema": "Finding relevant tables…",
    "run_sql": "Running SQL query…",
}


def _progress_events(update: dict) -> list[dict]:
    events = []
    for node, delta in update.items():
        for msg in (delta or {}).get("messages", []):
            if node == "agent" and isinstance(msg, AIMessage):
                for call in msg.tool_calls:
                    event = {"content": PROGRESS_LABELS.get(call["name"], f"Running {call['name']}…")}
                    if call["name"] == "run_sql":
                        event["sql"] = call["args"].get("query", "")
                    events.append(event)
            elif isinstance(msg, ToolMessage) and msg.name == "run_sql" and msg.artifact and "error" in msg.artifact:
                events.append({"content": "Query failed, retrying…", "error": msg.artifact["error"]})
    return events


def _answer_token(chunk: object, metadata: dict) -> str:
    if metadata.get("langgraph_node") != "agent":
        return ""
    if not isinstance(chunk, AIMessageChunk) or chunk.tool_call_chunks:
        return ""
    return chunk.content if isinstance(chunk.content, str) else ""


async def stream_turn(graph: CompiledStateGraph, thread_id: str, text: str) -> AsyncIterator[str]:
    turn_id = str(uuid4())
    yield sse({"type": "conversation_meta", "conversation_id": thread_id})
    yield sse({"type": "message_start", "message_id": turn_id, "role": "assistant"})

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
        "run_name": "chat_turn",
        "tags": ["api"],
        "metadata": {"thread_id": thread_id},
    }

    try:
        async for mode, chunk in graph.astream(
            {"messages": [HumanMessage(text)]},
            config,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                token = _answer_token(*chunk)
                if token:
                    yield sse({"type": "message_delta", "message_id": turn_id, "chunk": token})
            elif mode == "updates":
                for event in _progress_events(chunk):
                    yield sse({"type": "progress", "message_id": turn_id, **event})
    except asyncio.CancelledError:
        raise
    except GraphRecursionError:
        logger.warning("Recursion limit reached for thread %s", thread_id)
        yield sse({"type": "error", "message": "This question needed too many steps. Try rephrasing it."})
    except Exception:
        logger.exception("Chat turn failed for thread %s", thread_id)
        yield sse({"type": "error", "message": "Something went wrong while answering. Please try again."})

    yield sse({"type": "message_stop", "message_id": turn_id})
