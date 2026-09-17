from agent.db import get_admin_pool

TITLE_MAX_LENGTH = 60


def _title(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= TITLE_MAX_LENGTH else text[: TITLE_MAX_LENGTH - 1] + "…"


async def upsert_conversation(thread_id: str, first_message: str) -> None:
    pool = await get_admin_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (thread_id, title) VALUES (%s, %s)
            ON CONFLICT (thread_id) DO UPDATE SET updated_at = NOW()
            """,
            (thread_id, _title(first_message)),
        )


async def conversation_exists(thread_id: str) -> bool:
    pool = await get_admin_pool()
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT 1 FROM conversations WHERE thread_id = %s", (thread_id,))
        return await cur.fetchone() is not None


async def list_conversations(limit: int = 50) -> list[dict]:
    pool = await get_admin_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT thread_id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return await cur.fetchall()
