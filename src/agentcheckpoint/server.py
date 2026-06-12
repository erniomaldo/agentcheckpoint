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
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceTemplate,
    TextResourceContents,
)

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


# ── Embedded documentation resources ──────────────────────────────────────
# Agents can read these like files — no separate download needed.


DOCS = {
    "usage": """# AgentCheckpoint — Usage Patterns

## Single-Writer Pattern (cron jobs, solo agents)

Use `force_set_state` — it always succeeds and always replaces.

```python
mcp_checkpoint_force_set_state(
    key="workflow:daily-plan",
    value='{"phase": "research", "progress": 0.3}'
)
```

## Multi-Agent Coordination Pattern

Use `get_state` + `set_state` with the version guard (OCC).

```python
# 1. READ current state
state = mcp_checkpoint_get_state(key="workflow:plan-today")
plan = json.loads(state["value"])
# plan.current_index = 5

# 2. MODIFY — claim the next task
plan.current_index += 1
plan.current_task = "analisis"

# 3. WRITE with version guard
result = mcp_checkpoint_set_state(
    key="workflow:plan-today",
    value=json.dumps(plan),
    expected_version=state["version"]
)

if result["status"] == "conflict":
    # Another agent changed the state — retry from step 1
    pass
elif result["status"] == "ok":
    # We own this version now
    pass
```

Always pass `expected_version` when multiple agents write to the same key.
If you get a conflict, re-read and retry — that's the OCC pattern.

## Key Naming Convention

```
workflow:<id>           — Multi-step workflow state
project:<name>:<attr>   — Project-level attributes
lock:<resource>         — Distributed locks
plan:<date>             — Daily/periodic plans
checkpoint:<task>       — Task checkpoints
cron:<job-name>         — Cron job coordination
```

Use colons as separators. Keep keys semantic but short.
Values must be valid JSON strings.

## What NOT to Store

| ❌ Don't | ✅ Do |
|----------|-------|
| Facts, observations, learnings | agentmemory / vector store |
| Long text, documents | File system, RAG |
| Large JSON blobs (>100KB) | Split into multiple keys |
| Ephemeral task-local state | Keep in memory, write at boundaries |

AgentCheckpoint is for STATE COORDINATION, not memory.
Use both tools together: checkpoint for state, agentmemory for knowledge.

## Integration with Cron / Workers

```python
# Worker startup: check if work was already done
state = mcp_checkpoint_get_state(key="checkpoint:nocturno-2026-06-12")
if state["status"] != "not_found":
    print("Work already completed, skipping")
    return

# Worker claims and executes
mcp_checkpoint_force_set_state(
    key="checkpoint:nocturno-2026-06-12",
    value='{"status": "in-progress", "started_at": "..."}'
)

# ... do work ...

mcp_checkpoint_force_set_state(
    key="checkpoint:nocturno-2026-06-12",
    value='{"status": "completed", "finished_at": "..."}'
)
```
""",
    "coordination": """# Multi-Agent Coordination

AgentCheckpoint solves the "stale state" problem in multi-agent workflows.

## Problem

Agent A reads state, Agent B writes new state, Agent A writes based on its
stale read — overwriting B's work. This is the classic read-modify-write race.

## Solution: Optimistic Concurrency Control (OCC)

```python
# Every agent follows this pattern:

def claim_and_work(key, agent_id):
    while True:
        # READ with version
        current = mcp_checkpoint_get_state(key=key)
        if current["status"] == "not_found":
            # First claim
            result = mcp_checkpoint_set_state(
                key=key,
                value=json.dumps({"owner": agent_id, "step": 0}),
                expected_version=0  # create-only
            )
        else:
            plan = json.loads(current["value"])
            plan["owner"] = agent_id
            plan["step"] += 1
            # WRITE with version guard from the read
            result = mcp_checkpoint_set_state(
                key=key,
                value=json.dumps(plan),
                expected_version=current["version"]
            )

        if result["status"] == "ok":
            return result["version"]
        # conflict → re-read and retry
```

Each write carries the version observed at read time. If another agent
changed the key in between, the write fails with "conflict" and you retry.

## When to Skip Version Guard

Single-writer scenarios (cron jobs, solo agents, sequential workflows):
use `force_set_state` — no version check, always succeeds.

Multi-writer scenarios (multiple agents, parallel workers, distributed
systems): use `set_state` with `expected_version` — this is OCC.
""",
    "keys": """# Key Naming Convention

## Structure

```
<domain>:<identifier>[:<attribute>]
```

- **domain**: what kind of state (workflow, project, lock, plan, checkpoint, cron)
- **identifier**: unique name within that domain
- **attribute** (optional): sub-key for structured states

## Examples

| Key | Purpose |
|-----|---------|
| `workflow:daily-digest` | Multi-step workflow state |
| `project:agentcheckpoint:build-status` | Build state for a project |
| `lock:database-migration` | Mutex for a critical operation |
| `plan:2026-06-12` | Daily execution plan |
| `checkpoint:nocturno-pilar-1` | Nightly worker checkpoint |
| `cron:noticias-mañana` | Cron job coordination |

## Best Practices

- Use colons (`:`) as separators — they're readable and work with LIKE queries
- Keep keys under 200 chars
- Values must be valid JSON strings
- Use `list_state(pattern="project:%")` to find all project keys
- Group related keys with a common prefix for easy listing
""",
}


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return [
        Resource(
            uri="checkpoint://docs/usage",
            name="Usage Patterns",
            description="How to use agentcheckpoint: single-writer, multi-agent OCC, key naming, anti-patterns",
            mimeType="text/markdown",
        ),
        Resource(
            uri="checkpoint://docs/coordination",
            name="Multi-Agent Coordination",
            description="OCC pattern for multi-agent workflows with conflict detection",
            mimeType="text/markdown",
        ),
        Resource(
            uri="checkpoint://docs/keys",
            name="Key Naming Convention",
            description="Standard key structure and naming best practices",
            mimeType="text/markdown",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> TextResourceContents:
    parts = uri.split("://", 1)
    if len(parts) != 2 or parts[0] != "checkpoint":
        raise ValueError(f"Unknown resource: {uri}")

    doc_id = parts[1].removeprefix("docs/")
    content = DOCS.get(doc_id)
    if content is None:
        raise ValueError(f"Unknown documentation section: {doc_id}")

    return TextResourceContents(
        uri=uri,
        mimeType="text/markdown",
        text=content,
    )


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
