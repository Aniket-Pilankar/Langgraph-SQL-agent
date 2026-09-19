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


def _fixed_answer(update: dict) -> str:
    """Text from nodes that answer without an LLM call, so nothing reaches the token stream."""
    delta = update.get("give_up") or {}
    return "".join(m.content for m in delta.get("messages", []) if isinstance(m, AIMessage))


def _answer_token(chunk: object, metadata: dict) -> str:
    if metadata.get("langgraph_node") != "agent":
        return ""
    if not isinstance(chunk, AIMessageChunk) or chunk.tool_call_chunks:
        return ""
    return chunk.content if isinstance(chunk.content, str) else ""


def _block_event(chunk: dict, turn_id: str, index: int) -> dict | None:
    kind = chunk.get("kind")
    if kind == "block_start":
        return {"type": "block_start", "message_id": turn_id, "block_id": chunk["block_id"], "index": index}
    if kind == "block_delta":
        return {"type": "block_delta", "message_id": turn_id, "block_id": chunk["block_id"], "chunk": chunk["html"]}
    if kind == "block_stop":
        return {"type": "block_stop", "message_id": turn_id, "block_id": chunk["block_id"], "is_complete": chunk["ok"]}
    return None


async def _save_partial_answer(graph: CompiledStateGraph, config: dict, text: str) -> None:
    """Keep what the user already saw when they stop a turn. Checkpoints only commit
    completed nodes, so the streamed text would otherwise be lost."""
    try:
        await graph.aupdate_state(config, {"messages": [AIMessage(text)]}, as_node="widget")
    except Exception:
        logger.exception("Could not save the partial answer")


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
    answer = ""
    block_index = 0

    try:
        async for mode, chunk in graph.astream(
            {"messages": [HumanMessage(text)], "sql_attempts": 0},
            config,
            stream_mode=["messages", "updates", "custom"],
        ):
            if mode == "messages":
                token = _answer_token(*chunk)
                if token:
                    answer += token
                    yield sse({"type": "message_delta", "message_id": turn_id, "chunk": token})
            elif mode == "updates":
                for event in _progress_events(chunk):
                    yield sse({"type": "progress", "message_id": turn_id, **event})
                fixed = _fixed_answer(chunk)
                if fixed:
                    answer += fixed
                    yield sse({"type": "message_delta", "message_id": turn_id, "chunk": fixed})
            elif mode == "custom":
                event = _block_event(chunk, turn_id, block_index)
                if event:
                    if event["type"] == "block_start":
                        block_index += 1
                    yield sse(event)
    except asyncio.CancelledError:
        if answer:
            await asyncio.shield(_save_partial_answer(graph, config, answer))
        raise
    except GraphRecursionError:
        logger.warning("Recursion limit reached for thread %s", thread_id)
        yield sse({"type": "error", "message": "This question needed too many steps. Try rephrasing it."})
    except Exception:
        logger.exception("Chat turn failed for thread %s", thread_id)
        yield sse({"type": "error", "message": "Something went wrong while answering. Please try again."})

    yield sse({"type": "message_stop", "message_id": turn_id})
