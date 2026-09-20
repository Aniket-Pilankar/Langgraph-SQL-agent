"""Run the agent over the golden dataset and record an experiment in LangSmith.

Usage (from backend/):
    uv run python -m evals.run_eval --prefix baseline
    SCHEMA_EXEMPLARS=0 uv run python -m evals.run_eval --prefix no-exemplars
    AGENT_MODEL=gpt-4.1-mini uv run python -m evals.run_eval --prefix gpt-4.1-mini
"""

import argparse
import asyncio
import os
from collections import defaultdict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import aevaluate

from agent.db import close_pools
from agent.graph import RECURSION_LIMIT, build_graph, model_name
from agent.retrieval import DEFAULT_EXEMPLARS
from evals.build_dataset import DATASET_NAME
from evals.evaluators import EVALUATORS

_graph = None


async def target(inputs: dict) -> dict:
    result = await _graph.ainvoke(
        {"messages": [HumanMessage(inputs["question"])], "sql_attempts": 0},
        {"recursion_limit": RECURSION_LIMIT, "tags": ["eval"]},
    )
    messages = result["messages"]
    successful = [
        m.artifact
        for m in messages
        if isinstance(m, ToolMessage) and m.name == "run_sql" and m.artifact and "error" not in m.artifact
    ]
    return {
        "answer": messages[-1].content,
        "sql": successful[-1]["sql"] if successful else None,
        "rows": successful[-1]["rows"] if successful else None,
        "results": [artifact["rows"] for artifact in successful],
        "tool_calls": [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls],
        "sql_attempts": result.get("sql_attempts", 0),
    }


def _print_summary(scores: dict[str, list[int]]) -> None:
    print("\nScores")
    for key, values in scores.items():
        if values:
            print(f"  {key:<16} {sum(values) / len(values):6.1%}  ({sum(values)}/{len(values)})")


async def run(prefix: str, concurrency: int) -> None:
    global _graph
    _graph = build_graph()
    metadata = {
        "model": model_name(),
        "schema_exemplars": int(os.getenv("SCHEMA_EXEMPLARS", DEFAULT_EXEMPLARS)),
    }
    try:
        results = await aevaluate(
            target,
            data=DATASET_NAME,
            evaluators=EVALUATORS,
            experiment_prefix=prefix,
            max_concurrency=concurrency,
            metadata=metadata,
        )
        scores: dict[str, list[int]] = defaultdict(list)
        async for row in results:
            for evaluation in row["evaluation_results"]["results"]:
                if evaluation.score is not None:
                    scores[evaluation.key].append(int(evaluation.score))
        print(f"Experiment: {results.experiment_name}  {metadata}")
        _print_summary(scores)
    finally:
        await close_pools()
        wait_for_all_tracers()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="baseline")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    # psycopg async mode does not support the Windows ProactorEventLoop.
    asyncio.run(run(args.prefix, args.concurrency), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
