# AgentCheckpoint

**Atomic key-value state store MCP server for AI agent coordination.**

Stop your AI agents from working on stale state. AgentCheckpoint is a minimal
MCP (Model Context Protocol) server backed by SQLite that gives your agents
a shared, atomic state store — **always returning the latest written value**.

```bash
pip install agentcheckpoint
```

Then add to your MCP client:

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

## The Problem

Semantic memory stores (vector DBs, agentmemory, etc.) are designed for facts,
not state coordination. When multiple agents read/write shared state:

- `memory.save()` creates **new entries** instead of updating — dozens of stale
  versions accumulate
- `memory.recall()` returns results by **semantic similarity**, not by latest
  timestamp
- Agents read stale state and **re-execute completed work**

## The Solution — 100 lines of Python

AgentCheckpoint is a key-value store with atomic writes, **designed for state
coordination, not memory**.

- **Always latest** — `get_state(key)` returns the single current value
- **Atomic writes** — `force_set_state(key, value)` always updates, never appends
- **Conflict-safe** — `set_state(key, value, expected_version)` detects
  read-modify-write conflicts
- **SQLite-backed** — zero infrastructure, single file, WAL mode
- **One table, five tools** — simple enough to understand in 5 minutes

## Tools

| Tool | Description |
|------|-------------|
| `get_state` | Read the current value, version, and timestamp for a key |
| `set_state` | Write with optional version guard (OCC conflict detection) |
| `force_set_state` | Unconditional atomic write (for single-writer workflows) |
| `list_state` | List keys matching a SQL LIKE pattern |
| `delete_state` | Remove a key permanently |

## Quick Start

### 1. Install

```bash
pip install agentcheckpoint
# or
uv pip install agentcheckpoint
```

### 2. Add to your MCP client

Copy and paste the config for your platform. After adding, **restart your client**.

#### 🟣 Claude Desktop

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### 🔵 Claude Code

Add to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

Or use the CLI:

```bash
claude mcp add checkpoint -- python -m agentcheckpoint
```

#### 🟢 Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### 🟠 Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### ⚪ Continue.dev

Add to `~/.continue/config.json` under `experimental.mcpServers` (or `mcpServers` depending on version):

```json
{
  "experimental": {
    "mcpServers": {
      "checkpoint": {
        "command": "agentcheckpoint",
        "timeout": 10
      }
    }
  }
}
```

#### 🔶 Hermes Agent

Add to `~/.hermes/config.yaml` under `mcp_servers`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Then run `/reload-mcp` in-session, or restart the gateway.

#### 🐍 Any client with uvx support

If your client supports `uvx` (most modern clients do):

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "uvx",
      "args": ["agentcheckpoint"],
      "timeout": 10
    }
  }
}
```

### 3. Verify it works

Once configured, ask your agent:

> "What tools do I have from the checkpoint MCP server?"

You should see five tools: `get_state`, `set_state`, `force_set_state`, `list_state`, and `delete_state` (prefixed with `mcp_checkpoint_` in some clients).

### 4. Use it

```python
# Example: save and read a checkpoint
mcp_checkpoint_force_set_state(
    key="project:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Later...
status = mcp_checkpoint_get_state(key="project:build-status")
# → {value: {...}, version: 1, updated_at: "2026-06-12"}
```

## Example: Multi-Agent Coordination

```python
# Agent A reads the current plan
state = client.call_tool("get_state", {"key": "workflow:plan-today"})
plan = json.loads(state.value)
# plan.current_index = 5, plan.current_status = "completada"

# Agent A claims the next task
plan.current_index += 1  # now 6
plan.current_status = "en-progreso"
client.call_tool("force_set_state", {
    "key": "workflow:plan-today",
    "value": json.dumps(plan)
})

# ... Agent A works on the task ...

# Agent A marks it done
plan.tasks[6].status = "completada"
plan.current_status = "completada"
client.call_tool("force_set_state", {
    "key": "workflow:plan-today",
    "value": json.dumps(plan)
})

# Agent B (next tick) reads — always gets the latest
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | SQLite database path |

## Architecture

```
┌──────────────┐     MCP stdio     ┌──────────────────┐     SQLite WAL    ┌──────────┐
│  Agent /     │ ────────────────→ │  agentcheckpoint  │ ───────────────→ │ state.db │
│  Cron Worker │ ←──────────────── │  MCP Server       │ ←─────────────── │ (1 file) │
└──────────────┘                   └──────────────────┘                  └──────────┘
```

The server runs as a stdio subprocess. Tools are auto-discovered by the MCP
client. No network ports, no container, no configuration beyond adding it to
your `mcpServers`.

## Why not use agentmemory / vector store?

AgentCheckpoint is not a replacement for memory — it's a different tool for a
different job:

| | AgentCheckpoint | Vector/Semantic Memory |
|---|---|---|
| **Purpose** | State coordination | Facts, learning, retrieval |
| **Write** | Always replaces (UPDATE) | Always appends (INSERT) |
| **Read** | Exact key match (`SELECT WHERE key=?`) | Semantic similarity (`ORDER BY distance`) |
| **Concurrency** | Version guard (OCC) | None |
| **Persistence** | SQLite WAL (transactional) | Varies by backend |

**Use both together**: AgentCheckpoint for shared state (plans, checkpoints,
locks), vector memory for discoveries, observations, and facts.

## Development

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

## License

MIT

---

## Languages

- [Español](README.md)
- [Português](README.pt.md)
- [Français](README.fr.md)
