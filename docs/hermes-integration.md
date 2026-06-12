# Hermes Agent Integration

Add AgentCheckpoint as an MCP server in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Or from a local checkout:

```yaml
mcp_servers:
  checkpoint:
    command: "python3"
    args: ["/path/to/src/agentcheckpoint/server.py"]
    timeout: 10
```

After adding, run `/reload-mcp` or restart the gateway.

## Tool Names

All tools are prefixed with `mcp_checkpoint_`:

- `mcp_checkpoint_get_state`
- `mcp_checkpoint_set_state`
- `mcp_checkpoint_force_set_state`
- `mcp_checkpoint_list_state`
- `mcp_checkpoint_delete_state`

## Cron Job Toolsets

For cron jobs that need checkpoint access, include `mcp-checkpoint` in their
`enabled_toolsets`:

```yaml
enabled_toolsets:
  - terminal
  - file
  - mcp-checkpoint
```

## Migration from agentmemory

| Before (agentmemory) | After (agentcheckpoint) |
|----------------------|------------------------|
| `memory_recall(query="plan-2026-06-12")` | `get_state(key="plan-2026-06-12")` |
| `memory_save(content="plan-2026-06-12\\n{...}")` | `force_set_state(key="plan-2026-06-12", value=json.dumps({...}))` |
| Creates N entries per key | Always one row per key |

## Best Practices

- Use `force_set_state` for single-writer workflows (cron workers, sequential agents)
- Use `set_state` with `expected_version` for concurrent writers
- Keep agentmemory for facts, discoveries, and non-structural data
- Name keys with namespaces: `project:area:key`
