# Infrastructure Patrol Reference

For wu, maldoon, and infrastructure-focused agents.

## Critical Service Checklist

| Service | Container | Check |
|---------|-----------|-------|
| Dolt | ${DB_HOST} (236) | `service_health dolt-server` |
| Reactor | ${DB_HOST} (236) | `service_health reactor` |
| Prometheus | monitoring (212) | `service_health prometheus` |
| Alertmanager | monitoring (212) | `service_health alertmanager` |
| Grafana | monitoring (212) | `service_health grafana-server` |
| Traefik | proxy.lan (210) | `service_health traefik` |
| Forgejo | git.lan (224) | `service_health forgejo` |
| AdGuard | dns.lan (213) | `service_health AdGuardHome` |

## Prometheus Queries for Infrastructure

```promql
# Container CPU (host values may leak — known issue)
rate(node_cpu_seconds_total{mode="idle"}[5m])

# Memory usage per container
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes

# Disk usage
node_filesystem_avail_bytes{mountpoint="/"}

# Dolt connections
mysql_global_status_threads_connected  (if exporter exists)

# Service uptime
up{job=~".*"}
```

## Capacity Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Disk usage | >85% | >95% |
| Memory usage | >80% | >95% |
| CPU sustained | >70% 5min | >90% 5min |
| Dolt connections | >20 | >45 (max 50) |

## Known Issues (check before filing)

Before filing a new bead, check if the issue is already tracked:

```bash
bd list --json --status=open | python3 -c "
import json,sys
for b in json.load(sys.stdin):
    if 'keyword' in b['title'].lower():
        print(b['id'], b['title'])
"
```

Replace 'keyword' with the service or issue type you found.
