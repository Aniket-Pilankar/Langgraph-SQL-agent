"""Create or refresh the LangSmith golden dataset.

Reference rows are computed by running each reference query against the database,
so expected answers always match the loaded data.

Usage (from backend/):  uv run python -m evals.build_dataset
"""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langsmith import Client

from evals.normalize import normalize_row

DATASET_NAME = "olist-sql-golden"
GOLDEN_FILE = Path(__file__).parent / "golden.json"


def reference_rows(conn: psycopg.Connection, sql: str | None) -> list[list]:
    if not sql:
        return []
    return [normalize_row(row) for row in conn.execute(sql).fetchall()]


def build_examples(items: list[dict]) -> list[dict]:
    with psycopg.connect(os.environ["READONLY_DATABASE_URL"]) as conn:
        return [
            {
                "inputs": {"question": item["question"]},
                "outputs": {
                    "expected_rows": reference_rows(conn, item["reference_sql"]),
                    "reference_sql": item["reference_sql"],
                    "ordered": item["ordered"],
                    "must_mention": item["must_mention"],
                    "expects_sql": item["expects_sql"],
                    "expected_behavior": item.get("expected_behavior", ""),
                },
                "metadata": {"id": item["id"], "category": item["category"]},
            }
            for item in items
        ]


def main() -> None:
    load_dotenv()
    items = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    examples = build_examples(items)

    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        client.delete_dataset(dataset_name=DATASET_NAME)
    dataset = client.create_dataset(
        DATASET_NAME,
        description="Olist text-to-SQL questions with reference results computed from the database.",
    )
    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"Dataset '{DATASET_NAME}' created with {len(examples)} examples")


if __name__ == "__main__":
    main()
