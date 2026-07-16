# Bobbin Patrol Reference

For ian and search/context-focused agents.

## Bobbin Health Checklist

### Service Status

```text
mcp__homelab__service_health  container="tagi" service="bobbin"
```

### Index Health

```bash
# Check indexed repos and chunk counts
curl -sf http://tagi.lan:3000/healthz

# Check recent reindex activity
mcp__homelab__container_logs  container="tagi" service="bobbin" lines=20
```

### Injection Quality

Check recent bobbin injections in conversation — are they relevant?
Look for `[injection_id: ...]` tags in system-reminder blocks.

Key signals:

- **Good**: Injected chunks match the task context
- **Noise**: Injected chunks are unrelated to current work
- **Missing**: No injection when context would have helped

### Feedback System

```text
mcp__homelab__bobbin_feedback_stats
mcp__homelab__bobbin_feedback_list
```

Check feedback scores — low scores indicate injection quality issues.

## Prometheus Queries

```promql
# Bobbin service up
up{job="bobbin"}

# If bobbin exports metrics:
bobbin_index_chunks_total
bobbin_search_latency_seconds
```

## Common Issues

- **Stale index**: If repos were updated but bobbin didn't reindex,
  injections will reference old code. Check last reindex time.
- **Large file chunks**: Files >300 lines may produce low-quality chunks.
  Check chunk budget (default 300 lines) in bobbin config.
- **Pensieve sync**: Pensieve records on CT 215 auto-pull every 15min.
  If new records aren't appearing, check the crontab on CT 215.
