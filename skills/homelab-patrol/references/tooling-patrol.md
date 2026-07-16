# Tooling Patrol Reference

For arnold and tooling/DX-focused agents.

## Tooling Checklist

### CLI Tools

```bash
bd version          # beads CLI — check version, connectivity
gt version          # gastown CLI — check version
```

### Git Health

```bash
git status          # Clean workspace?
git log --oneline -5  # Recent commits look sane?
```

### CI Status

```promql
# GitHub CI status (1=passing, 0=failing)
github_ci_status

# Per-repo check
github_ci_status{repo="beads"}
github_ci_status{repo="gastown"}
github_ci_status{repo="bobbin"}
github_ci_status{repo="tapestry"}
```

### MCP Tools

```text
mcp__homelab__service_health  container="automation" service="homelab-mcp"
```

Quick verification: call any simple MCP tool and check it responds.

### Forgejo

```text
mcp__homelab__service_health  container="git.lan" service="forgejo"
mcp__homelab__forgejo_runs    repo="YOUR_ORG/aegis"
```

## Common Issues

- **bd list slow**: Text mode is 25-37s due to N+1 query. Always use `--json`
  when parsing programmatically (~0.16s).
- **Dolt pool exhaustion**: Under heavy multi-agent load, connections may
  max out (50 limit). Check `max_connections` if bd commands timeout.
- **MCP event loop blocking**: Fixed via asyncio.to_thread (aegis-wgr3cr).
  If MCP tools hang, check if blocking calls snuck back in.
- **GitHub CI failures**: gastown Windows CI, E2E, and Nightly may fail
  intermittently. Per guardrail: don't fix upstream unless blocking aegis.
