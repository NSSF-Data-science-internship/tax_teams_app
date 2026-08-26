import os
from pathlib import Path

from dotenv import load_dotenv


ENV_DIR = Path(__file__).resolve().parent.parent / "env"
load_dotenv(ENV_DIR / ".env.local", override=False)
load_dotenv(ENV_DIR / ".env", override=False)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "15432")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "taxpal")
POSTGRES_USER = os.getenv("POSTGRES_USER", "taxpal")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "taxpal_dev_password")
DATABASE_URL = os.getenv("CONVERSATION_DATABASE_URL", "").strip()

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

CREATE TABLE IF NOT EXISTS taxpal_conversations.user_memory (
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    consented BOOLEAN NOT NULL DEFAULT FALSE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    consented_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, channel)
);
"""


def _connect():
    import psycopg

    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, connect_timeout=5)
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DATABASE,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=5,
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
    )


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
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session_id, user_id, channel),
        )
        owner = connection.execute(
            """
            SELECT user_id, channel
            FROM taxpal_conversations.sessions
            WHERE session_id = %s
            """,
            (session_id,),
        ).fetchone()
        if owner != (user_id, channel):
            raise PermissionError("Conversation session belongs to a different user or channel.")
        connection.execute(
            "UPDATE taxpal_conversations.sessions SET updated_at = NOW() WHERE session_id = %s",
            (session_id,),
        )


def load_history(session_id: str, user_id: str, channel: str, limit: int = 12) -> list[dict]:
    ensure_schema()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT role, content, documents, diagnostics
            FROM (
                SELECT m.id, m.role, m.content, m.documents, m.diagnostics, m.created_at
                FROM taxpal_conversations.messages m
                JOIN taxpal_conversations.sessions s ON s.session_id = m.session_id
                WHERE m.session_id = %s AND s.user_id = %s AND s.channel = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY created_at ASC, id ASC
            """,
            (session_id, user_id, channel, limit),
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


def clear_history(session_id: str, user_id: str, channel: str) -> None:
    ensure_schema()
    with _connect() as connection:
        connection.execute(
            """
            DELETE FROM taxpal_conversations.sessions
            WHERE session_id = %s AND user_id = %s AND channel = %s
            """,
            (session_id, user_id, channel),
        )


def load_user_memory(user_id: str, channel: str) -> dict:
    ensure_schema()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT consented, preferences, consented_at, updated_at
            FROM taxpal_conversations.user_memory
            WHERE user_id = %s AND channel = %s
            """,
            (user_id, channel),
        ).fetchone()
    if not row:
        return {"consented": False, "preferences": {}}
    consented, preferences, consented_at, updated_at = row
    return {
        "consented": bool(consented),
        "preferences": preferences or {},
        "consented_at": consented_at.isoformat() if consented_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def set_memory_consent(user_id: str, channel: str, consented: bool) -> None:
    ensure_schema()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO taxpal_conversations.user_memory AS memory
                (user_id, channel, consented, consented_at)
            VALUES (%s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
            ON CONFLICT (user_id, channel) DO UPDATE SET
                consented = EXCLUDED.consented,
                consented_at = CASE
                    WHEN EXCLUDED.consented THEN COALESCE(memory.consented_at, NOW())
                    ELSE NULL
                END,
                preferences = CASE WHEN EXCLUDED.consented
                    THEN memory.preferences ELSE '{}'::jsonb END,
                updated_at = NOW()
            """,
            (user_id, channel, consented, consented),
        )


def update_user_memory(user_id: str, channel: str, preferences: dict) -> dict:
    from psycopg.types.json import Jsonb
    from user_memory import validate_preferences

    clean = validate_preferences(preferences)
    ensure_schema()
    with _connect() as connection:
        row = connection.execute(
            """
            UPDATE taxpal_conversations.user_memory
            SET preferences = preferences || %s, updated_at = NOW()
            WHERE user_id = %s AND channel = %s AND consented = TRUE
            RETURNING preferences
            """,
            (Jsonb(clean), user_id, channel),
        ).fetchone()
    if not row:
        raise PermissionError("Memory consent is required before saving profile details.")
    return row[0] or {}


def delete_user_memory(user_id: str, channel: str) -> None:
    ensure_schema()
    with _connect() as connection:
        connection.execute(
            "DELETE FROM taxpal_conversations.user_memory WHERE user_id = %s AND channel = %s",
            (user_id, channel),
        )
