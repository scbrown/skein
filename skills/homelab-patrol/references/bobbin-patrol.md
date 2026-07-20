# Search / Context Patrol Reference

For agents that own a code-search or context-injection service. Examples below use
[bobbin](https://github.com/scbrown/bobbin) (local-first code context engine); any
indexing search service patrols the same way.

## Health Checklist

### Service Status

```bash
systemctl is-active bobbin
curl -sf ${SEARCH_URL}/healthz
```

### Index Health

```bash
# Indexed repos and chunk counts
curl -sf ${SEARCH_URL}/healthz

# Recent reindex activity
journalctl -u bobbin -n 20 --no-pager
```

Ask when the index was last built, not whether the service is up. A perfectly
healthy service serving a three-week-old index is the failure mode here.

### Injection Quality

Check recent context injections in conversation — are they relevant?
Look for injection-id tags in the injected blocks.

Key signals:

- **Good**: injected chunks match the task context
- **Noise**: injected chunks are unrelated to current work
- **Missing**: no injection when context would have helped

Noise and Missing are both failures, and only one of them is visible. Sample
sessions deliberately; do not wait for someone to complain.

### Feedback Loop

If your search service records agent feedback, review the scores:

```bash
curl -sf ${SEARCH_URL}/feedback/stats
```

Low scores indicate injection-quality problems, not usage problems.

## Prometheus Queries

```promql
# Search service up
up{job="bobbin"}

# If it exports metrics:
bobbin_index_chunks_total
bobbin_search_latency_seconds
```

## Common Issues

- **Stale index**: if repos were updated but the indexer didn't run, injections
  reference code that no longer exists. Check the last reindex timestamp.
- **Oversized chunks**: files above a few hundred lines produce low-signal chunks.
  Check the chunk budget in the indexer config.
- **Broken sync job**: if records are pulled on a schedule and new ones stop
  appearing, check the cron entry on the host that runs it — a cron job that was
  clobbered by a non-appending `crontab -` edit fails silently forever.
