"""Run the agent from the command line.

Usage (from backend/):
    uv run python scripts/ask.py "How many orders were canceled?"
    uv run python scripts/ask.py --mermaid
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage  # noqa: E402
from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from agent.db import close_pools  # noqa: E402
from agent.graph import RECURSION_LIMIT, build_graph  # noqa: E402


async def ask(question: str) -> None:
    graph = build_graph()
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "run_name": "ask_cli",
        "tags": ["cli"],
        "metadata": {"question": question},
    }
    try:
        async for update in graph.astream({"messages": [HumanMessage(question)]}, config, stream_mode="updates"):
            for node, delta in update.items():
                for msg in delta["messages"]:
                    if node == "agent" and msg.tool_calls:
                        for tc in msg.tool_calls:
                            print(f"\n> {tc['name']}\n{tc['args'].get('query', '')}")
                    elif node == "agent":
                        print(f"\n{msg.content}")
                    elif msg.artifact and "error" in msg.artifact:
                        print(f"  error: {msg.artifact['error']}")
                    elif msg.name == "run_sql":
                        rows = msg.artifact.get("rows", [])
                        print(f"  {len(rows)} rows: {json.dumps(rows[:3], default=str)}")
    finally:
        await close_pools()
        wait_for_all_tracers()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--mermaid":
        print(build_graph().get_graph().draw_mermaid())
        sys.exit()
    question = " ".join(sys.argv[1:]) or "How many orders were canceled?"
    # psycopg async mode does not support the Windows ProactorEventLoop.
    asyncio.run(ask(question), loop_factory=asyncio.SelectorEventLoop)
