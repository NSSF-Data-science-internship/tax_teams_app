import os
from pathlib import Path

from dotenv import load_dotenv


ENV_DIR = Path(__file__).resolve().parent.parent / "env"
load_dotenv(ENV_DIR / ".env.local", override=False)
load_dotenv(ENV_DIR / ".env", override=False)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "15432")
DATABASE_URL = os.getenv(
    "CONVERSATION_DATABASE_URL",
    (
        "postgresql://taxpal:taxpal_dev_password@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/taxpal"
    ),
)

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS taxpal_conversations;

CREATE TABLE IF NOT EXISTS taxpal_conversations.sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS taxpal_conversations.messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES taxpal_conversations.sessions(session_id)
        ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    documents JSONB NOT NULL DEFAULT '[]'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS messages_session_created_idx
    ON taxpal_conversations.messages (session_id, created_at DESC);
"""


def _connect():
    import psycopg

    return psycopg.connect(DATABASE_URL)


def ensure_schema() -> None:
    with _connect() as connection:
        connection.execute(SCHEMA_SQL)


def register_session(session_id: str, user_id: str, channel: str) -> None:
    ensure_schema()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO taxpal_conversations.sessions (session_id, user_id, channel)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                channel = EXCLUDED.channel,
                updated_at = NOW()
            """,
            (session_id, user_id, channel),
        )


def load_history(session_id: str, limit: int = 12) -> list[dict]:
    ensure_schema()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT role, content, documents, diagnostics
            FROM (
                SELECT id, role, content, documents, diagnostics, created_at
                FROM taxpal_conversations.messages
                WHERE session_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY created_at ASC, id ASC
            """,
            (session_id, limit),
        ).fetchall()

    return [
        {
            "role": role,
            "content": content,
            "documents": documents or [],
            "diagnostics": diagnostics or {},
        }
        for role, content, documents, diagnostics in rows
    ]


def save_turn(
    session_id: str,
    user_id: str,
    channel: str,
    question: str,
    result: dict,
) -> None:
    from psycopg.types.json import Jsonb

    register_session(session_id, user_id, channel)
    diagnostics = {
        key: value
        for key, value in result.items()
        if key not in {"answer", "documents"}
    }

    with _connect() as connection:
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO taxpal_conversations.messages
                    (session_id, role, content)
                VALUES (%s, 'user', %s)
                """,
                (session_id, question),
            )
            connection.execute(
                """
                INSERT INTO taxpal_conversations.messages
                    (session_id, role, content, documents, diagnostics)
                VALUES (%s, 'assistant', %s, %s, %s)
                """,
                (
                    session_id,
                    result["answer"],
                    Jsonb(result.get("documents", [])),
                    Jsonb(diagnostics),
                ),
            )


def clear_history(session_id: str) -> None:
    ensure_schema()
    with _connect() as connection:
        connection.execute(
            "DELETE FROM taxpal_conversations.sessions WHERE session_id = %s",
            (session_id,),
        )
