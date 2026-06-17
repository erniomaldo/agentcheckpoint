# AgentCheckpoint

**Atomic key-value state store for AI agent coordination.**

[![PyPI - Version](https://img.shields.io/pypi/v/agentcheckpoint?style=flat-square&logo=pypi&color=blue)](https://pypi.org/project/agentcheckpoint/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/agentcheckpoint?style=flat-square&logo=python&color=yellow)](https://pypi.org/project/agentcheckpoint/)
[![License](https://img.shields.io/pypi/l/agentcheckpoint?style=flat-square&color=green)](https://github.com/erniomaldo/agentcheckpoint/blob/main/LICENSE)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/agentcheckpoint?style=flat-square&color=purple)](https://pypistats.org/packages/agentcheckpoint)
[![GitHub stars](https://img.shields.io/github/stars/erniomaldo/agentcheckpoint?style=flat-square&logo=github)](https://github.com/erniomaldo/agentcheckpoint)

---

<p align="center">
  <strong>An MCP server that stops your agents from working on stale state.</strong><br>
  <em>~150 lines of Python, SQLite WAL-backed, zero infrastructure.</em>
</p>

---

## 📦 Installation

```bash
pip install agentcheckpoint
```

Then add it to your MCP client of choice (jump to [Client Configuration](#-client-configuration)).

---

## 🤨 The Problem

Semantic memory stores —vector DBs, agentmemory, mem0, etc.— are designed for **facts and learning**, not **state coordination**. When multiple agents read and write shared state, here's what happens:

| Problem | What happens | Consequence |
|---------|-------------|-------------|
| `memory.save()` has no update | Each save creates a **new entry** | Dozens of stale versions pile up |
| `memory.recall()` uses similarity | Returns **semantically close** results, not the latest | Agents read outdated state |
| No concurrency control | Two agents read the same state, write without coordination | Changes overwrite each other, data loss |
| No version guard | One write can blindly overwrite another agent's work | **Corrupted workflows, re-executed work** |

**Bottom line:** your agents work with stale state, re-run tasks already completed, and burn compute on duplicated effort.

---

## ✅ The Solution

AgentCheckpoint is **not** a memory store — it's a **shared state store with atomic guarantees**. Think of it as a traffic light or shared memory for AI agents.

```
┌──────────────────────┐    MCP stdio    ┌────────────────────┐    SQLite WAL    ┌──────────────┐
│  Agent A              │ ───────────────→│                    │ ──────────────→│              │
│  Agent B              │ ───────────────→│  AgentCheckpoint   │ ──────────────→│  state.db    │
│  Cron Worker C        │ ───────────────→│  MCP Server        │ ──────────────→│  (1 file)    │
│  Pipeline D           │ ←──────────────│                    │ ←──────────────│              │
└──────────────────────┘                  └────────────────────┘                └──────────────┘
```

### How it compares

| Feature | AgentCheckpoint | agentmemory / vector DB | Redis | JSON file |
|---------|----------------|------------------------|-------|-----------|
| **Purpose** | State coordination | Facts, learning | Generic cache | Basic persistence |
| **Write** | Always replaces (UPSERT) | Always appends (INSERT) | Overwrites (no versioning) | Overwrites entire file |
| **Read** | `SELECT WHERE key=?` exact match | `ORDER BY distance` semantic | Direct key lookup | Parse & search |
| **Concurrency** | Optimistic Concurrency Control (OCC) | None | None native | None |
| **Persistence** | SQLite WAL (transactional, ACID) | Varies by backend | RAM / RDB / AOF | Filesystem-dependent |
| **Infrastructure** | Zero — single stdio process | Server, API, indices | Dedicated server | Zero |
| **MCP Tooling** | Native — auto-discovery of tools | No | No | No |
| **Lines of code** | ~150 | Thousands | ~50K+ | ~5 (no guarantees) |

**Use both together:** AgentCheckpoint for shared state, vector memory / agentmemory for facts, observations, and discoveries.

---

## 🛠️ Tools (MCP API)

| Tool | Description | When to use |
|------|-------------|-------------|
| `get_state(key)` | Read the current value, version, and timestamp for a key | Before any modification |
| `set_state(key, value, expected_version?)` | Write with optional version guard (OCC) | When **multiple** agents write the same key |
| `force_set_state(key, value)` | Unconditional atomic write | When a **single** agent/worker owns the key |
| `list_state(pattern?)` | List keys matching a SQL LIKE pattern | Auditing, discovery, debugging |
| `delete_state(key)` | Remove a key permanently | Cleanup of completed state |

Each tool is auto-discovered through the MCP protocol — no extra configuration needed.

> **Note for MCP clients:** in some clients tools are prefixed as `mcp_checkpoint_get_state`, `mcp_checkpoint_set_state`, etc.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install agentcheckpoint
# or with uv:
uv pip install agentcheckpoint
```

### 2. Add to your MCP client

Configuration varies by platform. After adding, **restart your client** or reload MCP servers.

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

Add to `~/.claude/settings.json`:

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

Or via CLI:

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

Add to `~/.continue/config.json`:

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

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Then run `/reload-mcp` in-session, or restart the gateway.

#### 🐍 Any client with uvx support

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

### 3. Verify

Ask your agent:

> _"What tools do I have from the checkpoint MCP server?"_

You should see all 5 tools listed above.

### 4. First checkpoint

```python
# Save state
mcp_checkpoint_force_set_state(
    key="project:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Read state later
status = mcp_checkpoint_get_state(key="project:build-status")
# → {status: "ok", key: "...", value: {...}, version: 1, updated_at: "2026-06-16T..."}
```

---

## 🎯 Usage Patterns

### Pattern 1: Single Writer (cron jobs, solo agents)

Use `force_set_state` — always succeeds, always replaces:

```python
# Nightly worker: checkpoint progress
mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "in-progress", "started_at": "2026-06-16T03:00:00Z"}'
)

# ... processing ...

mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "completed", "records_processed": 1427, "finished_at": "..."}'
)
```

### Pattern 2: Multiple Agents with OCC (the important one)

Use `get_state` + `set_state` with the version guard (Optimistic Concurrency Control):

```python
# 1. READ with version
current = mcp_checkpoint_get_state(key="workflow:plan-today")
plan = json.loads(current["value"])
# plan.current_index = 5, version = 3

# 2. MODIFY
plan.current_index += 1
plan.current_task = "analysis"

# 3. WRITE with the version we read
result = mcp_checkpoint_set_state(
    key="workflow:plan-today",
    value=json.dumps(plan),
    expected_version=current["version"]  # ← OCC guard
)

if result["status"] == "conflict":
    # Another agent changed the state → re-read and retry
    pass
elif result["status"] == "ok":
    # Write succeeded, new version assigned
    print(f"Checkpoint updated, version {result['version']}")
```

Each write carries the version observed at read time. If another agent changed the key in between, the write fails with `conflict` — you re-read and retry. This is standard **Optimistic Concurrency Control (OCC)**, the same pattern used by Elasticsearch, CouchDB, and Git.

### Pattern 3: Distributed Lock

```python
# Attempt to acquire a lock (create-only)
result = mcp_checkpoint_set_state(
    key="lock:db-migration",
    value=json.dumps({"owner": "agent-A", "acquired_at": "..."}),
    expected_version=0  # ← only works if it DOESN'T exist
)

if result["status"] == "ok":
    # Lock acquired — run critical operation
    run_migration()
    # Release
    mcp_checkpoint_delete_state(key="lock:db-migration")
else:
    # Lock held by another — wait or abort
    pass
```

### Pattern 4: Skip-if-done (idempotency guard)

```python
# Before starting: was this already completed?
state = mcp_checkpoint_get_state(key="checkpoint:generate-invoices")
if state["status"] != "not_found":
    print("Work already completed, skipping")
    return

# Claim + execute
mcp_checkpoint_force_set_state(
    key="checkpoint:generate-invoices",
    value='{"status": "started"}'
)
# ... do the work ...
```

---

## 📐 Key Naming Convention

Keep your keys organized with this structure:

```
<domain>:<identifier>[:<attribute>]
```

| Example | Purpose |
|---------|---------|
| `workflow:daily-digest` | Multi-step workflow state |
| `project:agentcheckpoint:build-status` | Build state for a project |
| `lock:database-migration` | Mutex for critical operation |
| `plan:2026-06-16` | Daily execution plan |
| `checkpoint:nocturnal-pillar-1` | Nightly worker checkpoint |
| `cron:news-morning` | Cron job coordination |

**Best practices:**
- Use colons (`:`) as separators — readable and work with `SELECT LIKE`
- Keep keys under **200 characters**
- Values **must always be valid JSON**
- Use `list_state(pattern="project:%")` to find all keys in a domain

---

## 📊 API Reference

### `get_state(key)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `string` | ✅ | Key to read |

**Success response:**
```json
{"status": "ok", "key": "workflow:plan", "value": "...", "version": 3, "updated_at": "2026-06-16T..."}
```

**Key not found:**
```json
{"status": "not_found", "key": "workflow:plan"}
```

### `set_state(key, value, expected_version?)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `string` | ✅ | Key to write |
| `value` | `string` | ✅ | Value (JSON string) |
| `expected_version` | `integer` | ❌ | -1=unconditional (default), 0=create-only, N=versioned update |

**Version guard behavior:**
| `expected_version` | Result |
|--------------------|--------|
| `-1` (omitted) | Always writes (like `force_set_state`) |
| `0` | Creates only if it DOESN'T exist. Fails with `conflict` if it does |
| `N > 0` | Updates only if stored version matches N. Fails with `conflict` if it doesn't |

### `force_set_state(key, value)`

Unconditional. Always writes. No version guard.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `string` | ✅ | Key to write |
| `value` | `string` | ✅ | Value (JSON string) |

### `list_state(pattern?)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pattern` | `string` | ❌ | SQL LIKE pattern (`%` = any text, `_` = single char). Default: `%` |

### `delete_state(key)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `string` | ✅ | Key to delete |

---

## ⚙️ Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | SQLite database file path |

Custom path example:

```bash
CHECKPOINT_DB_PATH=/tmp/my-state.db agentcheckpoint
```

---

## 🏗️ Architecture

```
┌──────────────────────┐       stdio (stdin/stdout)      ┌────────────────────┐
│                       │                                  │                    │
│  MCP Client           │ ────── JSON-RPC (MCP) ───────→  │  agentcheckpoint   │
│  (Claude, Cursor,     │ ←────────────────────────────── │  MCP Server        │
│   Windsurf, Hermes)   │                                  │                    │
│                       │                                  │  ┌──────────────┐  │
└──────────────────────┘                                  │  │  SQLite WAL   │  │
                                                          │  │  state.db     │  │
                                                          │  │  (1 file)     │  │
                                                          │  └──────────────┘  │
                                                          └────────────────────┘
```

### Technical details

- **Transport:** stdio (MCP subprocess) — no network ports, no containers
- **Database:** SQLite in WAL mode (Write-Ahead Logging) for concurrent reads without blocking
- **Concurrency:** `PRAGMA synchronous=NORMAL` — balance between durability and speed
- **Validation:** all values validated as JSON on write
- **Versioning:** every UPSERT atomically increments the version counter
- **Connection timeout:** 5 seconds in SQLite, 10 seconds recommended in MCP client
- **Atomicity:** writes are transactional — either fully persisted or not persisted at all

---

## ❓ FAQ

**Q: Does AgentCheckpoint replace agentmemory?**
A: No. They're complementary. AgentCheckpoint coordinates state (who did what? which step are we on?). agentmemory stores facts and learnings (what did we discover? how does X work?). **Use both together.**

**Q: Can I run multiple instances pointing at the same file?**
A: SQLite WAL supports multiple concurrent readers, but for multiple writers it's best to use a single MCP server instance. For high availability, consider placing the `.db` on a shared volume.

**Q: What if the process crashes mid-write?**
A: SQLite WAL guarantees atomicity — either the full change is persisted or nothing is. No partial writes.

**Q: How large can a value be?**
A: Values are JSON strings. SQLite can theoretically handle up to ~1GB, but we recommend keeping values under **100KB**. For large data, store a reference (file path, URL) as the value.

**Q: How do I clean up old checkpoints?**
A: Use `delete_state` for individual keys or write a script that iterates with `list_state` and deletes based on `updated_at`.

**Q: Does it support TTL / auto-expiration?**
A: Not natively, but you can implement it in your agent: when reading, check `updated_at` and decide if the state is stale.

---

## 🧑‍💻 Development

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

Source code lives in `src/agentcheckpoint/`:

| File | What it does |
|------|-------------|
| `__init__.py` | Package version |
| `__main__.py` | Entry point (`python -m agentcheckpoint`) |
| `server.py` | Complete MCP server (~150 lines) |

### Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/awesome-thing`)
3. Make your changes
4. Commit with clear messages
5. Push and open a Pull Request

---

## 📜 License

MIT © [Ernesto Maldonado](https://github.com/erniomaldo)

---

## 🌐 Languages

| Language | File |
|----------|------|
| 🇺🇸 English | `README.en.md` (this) |
| 🇪🇸 Español | [`README.md`](README.md) |
| 🇫🇷 Français | [`README.fr.md`](README.fr.md) |
| 🇧🇷 Português | [`README.pt.md`](README.pt.md) |

---

<p align="center">
  <sub>Made with ❤️ to keep agents from stepping on each other's state.</sub><br>
  <sub>Found it useful? Drop a ⭐ on <a href="https://github.com/erniomaldo/agentcheckpoint">GitHub</a></sub>
</p>
