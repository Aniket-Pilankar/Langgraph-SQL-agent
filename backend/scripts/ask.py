"""Run the agent from the command line.

Usage (from backend/):
    uv run python -m scripts.ask "How many orders were canceled?"
    uv run python -m scripts.ask --mermaid
"""

import asyncio
import json
import sys

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tracers.langchain import wait_for_all_tracers

from agent.db import close_pools
from agent.graph import RECURSION_LIMIT, build_graph


def _print_message(msg) -> None:
    if isinstance(msg, AIMessage) and msg.tool_calls:
        for call in msg.tool_calls:
            print(f"\n> {call['name']}\n{call['args'].get('query', '')}")
    elif isinstance(msg, AIMessage):
        print(f"\n{msg.content}")
    elif isinstance(msg, ToolMessage) and msg.artifact and "error" in msg.artifact:
        print(f"  error: {msg.artifact['error']}")
    elif isinstance(msg, ToolMessage) and msg.name == "run_sql":
        rows = msg.artifact.get("rows", [])
        print(f"  {len(rows)} rows: {json.dumps(rows[:3], default=str)}")


async def ask(question: str) -> None:
    graph = build_graph()
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "run_name": "ask_cli",
        "tags": ["cli"],
        "metadata": {"question": question},
    }
    try:
        async for update in graph.astream(
            {"messages": [HumanMessage(question)], "sql_attempts": 0}, config, stream_mode="updates"
        ):
            for node, delta in update.items():
                delta = delta or {}
                for msg in delta.get("messages", []):
                    _print_message(msg)
                if "sql_attempts" in delta:
                    print(f"  failed queries this turn: {delta['sql_attempts']}")
                if delta.get("widgets"):
                    print(f"  [{node}] widget rendered")
    finally:
        await close_pools()
        wait_for_all_tracers()


def main() -> None:
    load_dotenv()
    if len(sys.argv) > 1 and sys.argv[1] == "--mermaid":
        print(build_graph().get_graph().draw_mermaid())
        return
    question = " ".join(sys.argv[1:]) or "How many orders were canceled?"
    # psycopg async mode does not support the Windows ProactorEventLoop.
    asyncio.run(ask(question), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
