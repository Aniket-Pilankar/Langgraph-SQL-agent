from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.conversations import conversation_exists, list_conversations, upsert_conversation
from app.streaming import stream_turn

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


@router.post("/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    thread_id = str(body.conversation_id or uuid4())
    message = body.message.strip()
    await upsert_conversation(thread_id, message)
    return StreamingResponse(
        stream_turn(request.app.state.graph, thread_id, message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
async def get_conversations() -> list[dict]:
    return await list_conversations()


@router.get("/conversations/{thread_id}/messages")
async def get_messages(thread_id: UUID, request: Request) -> list[dict]:
    if not await conversation_exists(str(thread_id)):
        raise HTTPException(status_code=404, detail="Conversation not found")

    snapshot = await request.app.state.graph.aget_state({"configurable": {"thread_id": str(thread_id)}})
    widgets: dict[str, list[str]] = {}
    for widget in snapshot.values.get("widgets", []):
        widgets.setdefault(widget["message_id"], []).append(widget["html"])

    messages = []
    for msg in snapshot.values.get("messages", []):
        if isinstance(msg, HumanMessage):
            messages.append({"id": msg.id, "role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
            messages.append({
                "id": msg.id,
                "role": "assistant",
                "content": msg.content,
                "widgets": widgets.get(msg.id, []),
            })
    return messages
