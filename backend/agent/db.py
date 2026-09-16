import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_readonly_pool: AsyncConnectionPool | None = None
_admin_pool: AsyncConnectionPool | None = None


async def get_readonly_pool() -> AsyncConnectionPool:
    """Pool for agent-generated SQL (agent_readonly role)."""
    global _readonly_pool
    if _readonly_pool is None:
        _readonly_pool = AsyncConnectionPool(
            os.environ["READONLY_DATABASE_URL"],
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await _readonly_pool.open()
    return _readonly_pool


async def get_admin_pool() -> AsyncConnectionPool:
    """Pool for app tables, schema memory and the checkpointer."""
    global _admin_pool
    if _admin_pool is None:
        _admin_pool = AsyncConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await _admin_pool.open()
    return _admin_pool


async def close_pools() -> None:
    global _readonly_pool, _admin_pool
    for pool in (_readonly_pool, _admin_pool):
        if pool is not None:
            await pool.close()
    _readonly_pool = _admin_pool = None
