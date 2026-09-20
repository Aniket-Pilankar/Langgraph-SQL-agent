import json
import logging
import operator
import os
from functools import cache
from typing import Annotated, Literal
from uuid import uuid4

import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agent.prompts import SYSTEM_PROMPT, WIDGET_PROMPT
from agent.tools import TOOLS
from agent.widgets import WidgetChoice, build_widget_html, is_chartable, last_sql_result

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
RECURSION_LIMIT = 20
MAX_SQL_ATTEMPTS = 3
WIDGET_SAMPLE_ROWS = 3
LLM_ATTEMPTS = 3

# Some network edges in front of the OpenAI API intermittently answer valid requests
# with an empty-body 404. The SDK only retries 408/409/429/5xx, so retry these too.
_TRANSIENT_ERRORS = (openai.NotFoundError,)


def model_name() -> str:
    return os.getenv("AGENT_MODEL", DEFAULT_MODEL)


@cache
def get_llm() -> BaseChatModel:
    return ChatOpenAI(model=model_name(), temperature=0)


@cache
def get_llm_with_tools() -> Runnable:
    return get_llm().bind_tools(TOOLS).with_retry(
        retry_if_exception_type=_TRANSIENT_ERRORS, stop_after_attempt=LLM_ATTEMPTS
    )


@cache
def get_widget_llm() -> Runnable:
    return get_llm().with_structured_output(WidgetChoice).with_retry(
        retry_if_exception_type=_TRANSIENT_ERRORS, stop_after_attempt=LLM_ATTEMPTS
    )


class AgentState(MessagesState):
    widgets: Annotated[list[dict], operator.add]
    sql_attempts: int


def repair_dangling_tool_calls(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Add placeholder results for tool calls that never ran, which happens when a turn
    is cancelled mid-execution. Without them the model rejects the history."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    repaired: list[AnyMessage] = []
    for msg in messages:
        repaired.append(msg)
        if isinstance(msg, AIMessage):
            repaired.extend(
                ToolMessage(content="Cancelled before this tool ran.", tool_call_id=call["id"], name=call["name"])
                for call in msg.tool_calls
                if call["id"] not in answered
            )
    return repaired


def _latest_tool_messages(messages: list[AnyMessage]) -> list[ToolMessage]:
    latest: list[ToolMessage] = []
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            break
        latest.append(msg)
    return latest


def _sql_errors(messages: list[AnyMessage]) -> list[str]:
    return [
        m.artifact["error"]
        for m in _latest_tool_messages(messages)
        if m.name == "run_sql" and m.artifact and "error" in m.artifact
    ]


async def agent_node(state: AgentState) -> dict:
    messages = repair_dangling_tool_calls(state["messages"])
    response = await get_llm_with_tools().ainvoke([SystemMessage(SYSTEM_PROMPT), *messages])
    return {"messages": [response]}


async def check_sql_node(state: AgentState) -> dict:
    failures = len(_sql_errors(state["messages"]))
    if not failures:
        return {}
    return {"sql_attempts": state.get("sql_attempts", 0) + failures}


async def give_up_node(state: AgentState) -> dict:
    errors = _sql_errors(state["messages"])
    detail = f" The last database error was: {errors[-1].rstrip('.')}." if errors else ""
    return {
        "messages": [
            AIMessage(
                f"I couldn't build a working query for that after {MAX_SQL_ATTEMPTS} attempts.{detail} "
                "Try rephrasing the question, or ask about orders, customers, products, sellers, "
                "payments or reviews."
            )
        ]
    }


async def widget_node(state: AgentState) -> dict:
    messages = state["messages"]
    artifact = last_sql_result(messages)
    if not is_chartable(artifact):
        return {}

    question = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    answer_id = messages[-1].id
    block_id = str(uuid4())

    writer = get_stream_writer()
    writer({"kind": "block_start", "block_id": block_id})

    try:
        choice = await get_widget_llm().ainvoke(
            WIDGET_PROMPT.format(
                question=question,
                columns=", ".join(artifact["columns"]),
                sample_rows=json.dumps(artifact["rows"][:WIDGET_SAMPLE_ROWS], default=str),
                row_count=artifact["row_count"],
            )
        )
        widget_html = build_widget_html(choice, artifact)
    except Exception:
        logger.exception("Widget generation failed")
        widget_html = None

    if not widget_html:
        writer({"kind": "block_stop", "block_id": block_id, "ok": False})
        return {}

    writer({"kind": "block_delta", "block_id": block_id, "html": widget_html})
    writer({"kind": "block_stop", "block_id": block_id, "ok": True})
    return {"widgets": [{"message_id": answer_id, "html": widget_html}]}


def route_after_agent(state: AgentState) -> Literal["tools", "widget", "__end__"]:
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    if is_chartable(last_sql_result(state["messages"])):
        return "widget"
    return END


def route_after_check(state: AgentState) -> Literal["agent", "give_up"]:
    if state.get("sql_attempts", 0) >= MAX_SQL_ATTEMPTS:
        return "give_up"
    return "agent"


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_node("check_sql", check_sql_node)
    builder.add_node("give_up", give_up_node)
    builder.add_node("widget", widget_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent, ["tools", "widget", END])
    builder.add_edge("tools", "check_sql")
    builder.add_conditional_edges("check_sql", route_after_check, ["agent", "give_up"])
    builder.add_edge("give_up", END)
    builder.add_edge("widget", END)

    return builder.compile(checkpointer=checkpointer)
