import json
import re
from datetime import date, datetime
from decimal import Decimal

from langchain_core.tools import tool

from agent.db import get_readonly_pool
from agent.retrieval import search_schema_memory

MAX_ROWS = 100

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|vacuum|merge|call|do)\b",
    re.IGNORECASE,
)


@tool
async def retrieve_schema(query: str) -> str:
    """Find the relevant tables, their exact columns, and example SQL queries for a question.
    ALWAYS call this before run_sql so you use correct column names and conventions.

    Args:
        query: short description of the data needed, e.g. 'revenue by product category'.
    """
    docs = await search_schema_memory(query)
    if not docs:
        return "No schema memory found. Tables: customers, orders, order_items, products, sellers, payments, reviews."
    cards = [d["page_content"] for d in docs if d["metadata"]["kind"] == "card"]
    examples = [d["page_content"] for d in docs if d["metadata"]["kind"] == "exemplar"]
    return (
        "RELEVANT TABLES:\n\n" + "\n\n".join(cards)
        + "\n\nEXAMPLE QUERIES (follow these conventions):\n\n" + "\n\n".join(examples)
    )


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def validate_sql(query: str) -> str | None:
    """Return an error message if the query is not an allowed read-only SELECT."""
    q = query.strip().rstrip(";").strip()
    if not q:
        return "Empty query."
    if ";" in q:
        return "Only a single SQL statement is allowed."
    if not re.match(r"^(select|with)\b", q, re.IGNORECASE):
        return "Only SELECT queries are allowed."
    if _FORBIDDEN.search(q):
        return "Query contains a forbidden keyword. Read-only SELECT only."
    return None


@tool(response_format="content_and_artifact")
async def run_sql(query: str) -> tuple[str, dict]:
    """Run ONE read-only PostgreSQL SELECT against the Olist database and return the rows.
    Call retrieve_schema first. Prefer aggregates; at most 100 rows are returned.

    Args:
        query: a single PostgreSQL SELECT statement.
    """
    error = validate_sql(query)
    if error:
        return json.dumps({"error": error}), {"sql": query, "error": error}

    q = query.strip().rstrip(";").strip()
    wrapped = f"SELECT * FROM ({q}) AS agent_query LIMIT {MAX_ROWS + 1}"

    pool = await get_readonly_pool()
    try:
        async with pool.connection() as conn:
            cur = await conn.execute(wrapped)
            rows = await cur.fetchall()
            columns = [c.name for c in cur.description] if cur.description else []
    except Exception as e:
        # Returned to the model so it can correct the query.
        msg = str(e).strip()
        return json.dumps({"error": msg}), {"sql": q, "error": msg}

    truncated = len(rows) > MAX_ROWS
    data = [{k: _jsonable(v) for k, v in r.items()} for r in rows[:MAX_ROWS]]
    result = {"columns": columns, "rows": data, "row_count": len(data), "truncated": truncated}
    return json.dumps(result, default=str), {"sql": q, **result}


TOOLS = [retrieve_schema, run_sql]
