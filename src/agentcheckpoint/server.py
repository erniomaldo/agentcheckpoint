"""AgentCheckpoint — Atomic key-value state store for AI agent coordination.

MCP (Model Context Protocol) server backed by SQLite for checkpoint coordination
between AI agents, cron workers, or any multi-agent workflow. Each key holds a
JSON value. Reads always return the latest written value — no semantic ambiguity,
no stale entries, no race conditions.

Usage:
    agentcheckpoint                          # stdio MCP server
    CHECKPOINT_DB_PATH=/tmp/state.db agentcheckpoint  # custom DB path
"""

from __future__ import annotations

import json
import os
import sqlite3

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

DB_PATH = os.environ.get(
    "CHECKPOINT_DB_PATH",
    os.path.expanduser("~/.hermes/checkpoints.db"),
)

server = Server("agentcheckpoint")


def get_db() -> sqlite3.Connection:
    """Get a WAL-mode SQLite connection. Creates the table if missing."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS checkpoints (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    return conn


def _validate_json(value: str) -> str | None:
    """Return error message if value is not valid JSON, else None."""
    try:
        json.loads(value)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    return None


def _upsert(conn: sqlite3.Connection, key: str, value: str) -> int:
    """Insert or replace a key's value atomically, incrementing version."""
    conn.execute(
        """INSERT INTO checkpoints (key, value, version, updated_at)
           VALUES (?, ?, 1, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
               value = excluded.value,
               version = checkpoints.version + 1,
               updated_at = datetime('now')""",
        (key, value),
    )
    conn.commit()
    row = conn.execute(
        "SELECT version FROM checkpoints WHERE key = ?", (key,)
    ).fetchone()
    return row["version"]


# ── Tool definitions ──────────────────────────────────────────────────────


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_state",
            description=(
                "Read the current value of a checkpoint by key. "
                "Returns the latest stored JSON value, its version, and update timestamp. "
                'Returns {"status": "not_found"} if key doesn\'t exist.'
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Checkpoint key, e.g. 'workflow:plan-2026-06-12'",
                    }
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="set_state",
            description=(
                "Atomically write a checkpoint with optional version guard. "
                "Pass expected_version from a prior get_state call. "
                "expected_version=0 → create-only (fails if key exists). "
                "expected_version=N → update only if stored version matches (conflict-safe). "
                "Omit expected_version or pass -1 → unconditional write. "
                "Use force_set_state for simpler unconditional writes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Checkpoint key"},
                    "value": {
                        "type": "string",
                        "description": "Value to store (must be JSON-encoded string)",
                    },
                    "expected_version": {
                        "type": "integer",
                        "description": "Version guard: -1=unconditional, 0=create-only, N=versioned update",
                        "default": -1,
                    },
                },
                "required": ["key", "value"],
            },
        ),
        Tool(
            name="force_set_state",
            description=(
                "Unconditionally write a checkpoint value. "
                "Always succeeds. Prefer for single-writer workflows. "
                "For concurrent writers, use set_state with expected_version."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Checkpoint key"},
                    "value": {
                        "type": "string",
                        "description": "Value to store (must be JSON-encoded string)",
                    },
                },
                "required": ["key", "value"],
            },
        ),
        Tool(
            name="list_state",
            description=(
                "List checkpoint keys matching a pattern (SQL LIKE syntax). "
                "Pass '%' or omit for all keys. Returns key, version, and updated_at for each match."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern (default '%' = all keys)",
                        "default": "%",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="delete_state",
            description="Remove a checkpoint key and its value permanently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Checkpoint key to delete",
                    }
                },
                "required": ["key"],
            },
        ),
    ]


# ── Tool call dispatcher ──────────────────────────────────────────────────


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    def ok(data: dict) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps(data))]

    conn = get_db()
    try:
        if name == "get_state":
            key = arguments["key"]
            row = conn.execute(
                "SELECT value, version, updated_at FROM checkpoints WHERE key = ?",
                (key,),
            ).fetchone()
            if row:
                return ok({
                    "status": "ok",
                    "key": key,
                    "value": row["value"],
                    "version": row["version"],
                    "updated_at": row["updated_at"],
                })
            return ok({"status": "not_found", "key": key})

        elif name == "set_state":
            key = arguments["key"]
            value = arguments["value"]
            expected_version = arguments.get("expected_version", -1)

            err = _validate_json(value)
            if err:
                return ok({"status": "error", "message": err})

            if expected_version == -1:
                version = _upsert(conn, key, value)
                return ok({"status": "ok", "key": key, "version": version})

            row = conn.execute(
                "SELECT version FROM checkpoints WHERE key = ?", (key,)
            ).fetchone()

            if expected_version == 0:
                if row is not None:
                    return ok({
                        "status": "conflict",
                        "key": key,
                        "message": f"Key already exists (version={row['version']}). Use expected_version=N to update, or force_set_state.",
                        "actual_version": row["version"],
                    })
                conn.execute(
                    "INSERT INTO checkpoints (key, value, version, updated_at) VALUES (?, ?, 1, datetime('now'))",
                    (key, value),
                )
                conn.commit()
                return ok({"status": "ok", "key": key, "version": 1})

            if row is None:
                return ok({
                    "status": "not_found",
                    "key": key,
                    "message": "Key does not exist. Use expected_version=0 to create, or force_set_state.",
                })
            if row["version"] != expected_version:
                return ok({
                    "status": "conflict",
                    "key": key,
                    "expected_version": expected_version,
                    "actual_version": row["version"],
                    "message": f"Version mismatch: expected {expected_version}, actual {row['version']}. Call get_state and retry.",
                })
            conn.execute(
                "UPDATE checkpoints SET value = ?, version = version + 1, updated_at = datetime('now') WHERE key = ? AND version = ?",
                (value, key, expected_version),
            )
            conn.commit()
            new_row = conn.execute(
                "SELECT version FROM checkpoints WHERE key = ?", (key,)
            ).fetchone()
            return ok({"status": "ok", "key": key, "version": new_row["version"]})

        elif name == "force_set_state":
            key = arguments["key"]
            value = arguments["value"]

            err = _validate_json(value)
            if err:
                return ok({"status": "error", "message": err})

            version = _upsert(conn, key, value)
            return ok({"status": "ok", "key": key, "version": version})

        elif name == "list_state":
            pattern = arguments.get("pattern", "%")
            rows = conn.execute(
                "SELECT key, version, updated_at FROM checkpoints WHERE key LIKE ? ORDER BY key",
                (pattern,),
            ).fetchall()
            return ok({
                "status": "ok",
                "keys": [
                    {"key": r["key"], "version": r["version"], "updated_at": r["updated_at"]}
                    for r in rows
                ],
            })

        elif name == "delete_state":
            key = arguments["key"]
            conn.execute("DELETE FROM checkpoints WHERE key = ?", (key,))
            conn.commit()
            return ok({"status": "ok", "key": key, "deleted": True})

        else:
            return ok({"status": "error", "message": f"Unknown tool: {name}"})

    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────


async def main_async() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Run the agentcheckpoint MCP server over stdio."""
    import asyncio
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
