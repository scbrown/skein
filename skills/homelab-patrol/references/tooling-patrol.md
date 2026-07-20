# Tooling Patrol Reference

For tooling / developer-experience agents: CLIs, CI, git hygiene, MCP health.

## Tooling Checklist

### CLI Tools

```bash
<tracker> version   # issue tracker CLI — check version and connectivity
<agent-cli> version # agent/workspace CLI — check version
```

Check *connectivity*, not just that the binary answers. A CLI that prints its
version while its backing store is unreachable looks perfectly healthy.

### Git Health

```bash
git status            # Clean workspace?
git log --oneline -5  # Recent commits look sane?
```

### CI Status

```promql
# CI status (1=passing, 0=failing), if you export it
ci_status

# Per-repo check
ci_status{repo="search-api"}
ci_status{repo="dashboard"}
```

### MCP Tools

```bash
systemctl is-active ops-mcp
# then call any cheap MCP tool and confirm it responds
```

A server that accepts a connection is not a server that serves. Call a real
tool.

### Git Hosting

```bash
curl -sf https://git.example.com/api/healthz
# check recent CI runs for the repos you own
```

## Common Issues

- **Slow list commands**: text-mode output in some trackers does an N+1 query and
  takes tens of seconds. Use `--json` when parsing programmatically — often two
  orders of magnitude faster.
- **DB connection pool exhaustion**: under heavy multi-agent load, connections max
  out and every CLI call hangs. Check `max_connections` before blaming the CLI.
- **Async event-loop blocking**: a synchronous call inside an async MCP handler
  blocks every other tool call on that server. If MCP tools hang under load, look
  for blocking calls that snuck back in (`asyncio.to_thread` is the usual fix).
- **Upstream CI flakes**: some upstream matrix jobs (Windows, E2E, nightly) fail
  intermittently. Don't chase upstream failures unless they block *your* work.
