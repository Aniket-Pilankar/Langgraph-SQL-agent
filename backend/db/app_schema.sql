CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_memory (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind        TEXT        NOT NULL CHECK (kind IN ('card', 'exemplar')),
    table_name  TEXT,
    content     TEXT        NOT NULL,
    embedding   vector(512) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversation messages are stored by the LangGraph checkpointer; this table
-- only indexes threads for listing.
CREATE TABLE IF NOT EXISTS conversations (
    thread_id   UUID        PRIMARY KEY,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
