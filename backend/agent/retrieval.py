from langchain_openai import OpenAIEmbeddings
from langsmith import traceable

from agent.db import get_admin_pool

_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=512)

_SEARCH_SQL = """
    SELECT kind, table_name, content,
           ROUND((1 - (embedding <=> %(qvec)s::vector))::numeric, 4) AS similarity
    FROM schema_memory
    WHERE kind = %(kind)s
    ORDER BY embedding <=> %(qvec)s::vector
    LIMIT %(k)s
"""


@traceable(run_type="retriever", name="schema_memory_search")
async def search_schema_memory(query: str, n_cards: int = 4, n_exemplars: int = 3) -> list[dict]:
    """Return the closest table cards and exemplars as Document-shaped dicts."""
    qvec = "[" + ",".join(map(str, await _embeddings.aembed_query(query))) + "]"

    pool = await get_admin_pool()
    async with pool.connection() as conn:
        cards = await (await conn.execute(_SEARCH_SQL, {"qvec": qvec, "kind": "card", "k": n_cards})).fetchall()
        exemplars = await (await conn.execute(_SEARCH_SQL, {"qvec": qvec, "kind": "exemplar", "k": n_exemplars})).fetchall()

    return [
        {
            "page_content": row["content"],
            "type": "Document",
            "metadata": {"kind": row["kind"], "table": row["table_name"], "similarity": float(row["similarity"])},
        }
        for row in [*cards, *exemplars]
    ]
