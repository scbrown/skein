# Infrastructure Patrol Reference

For infrastructure-focused agents: services, alerts, capacity, host health.

## Critical Service Checklist

Replace the example rows with your own fleet — the point is that the list lives in
a file an agent can read, not in someone's memory.

| Service | Host | Check |
|---------|------|-------|
| Database | ${DB_HOST} | `systemctl is-active db-server` |
| Event daemon | ${DB_HOST} | `systemctl is-active eventd` |
| Prometheus | monitor01 | `systemctl is-active prometheus` |
| Alertmanager | monitor01 | `systemctl is-active alertmanager` |
| Grafana | monitor01 | `systemctl is-active grafana-server` |
| Traefik | proxy01 | `systemctl is-active traefik` |
| Git hosting | git.example.com | `systemctl is-active forgejo` |
| DNS | dns01 | `systemctl is-active AdGuardHome` |

## Prometheus Queries for Infrastructure

```promql
# CPU (in a container fleet, host values can leak into container metrics — verify)
rate(node_cpu_seconds_total{mode="idle"}[5m])

# Memory usage per host
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes

# Disk usage
node_filesystem_avail_bytes{mountpoint="/"}

# Database connections (if an exporter exists)
mysql_global_status_threads_connected

# Service uptime
up{job=~".*"}
```

## Capacity Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Disk usage | >85% | >95% |
| Memory usage | >80% | >95% |
| CPU sustained | >70% 5min | >90% 5min |
| DB connections | >40% of max | >90% of max |

## Known Issues (check before filing)

Before filing a new issue, check whether it is already tracked:

```bash
<tracker> list --json --status=open | python3 -c "
import json,sys
for b in json.load(sys.stdin):
    if 'keyword' in b['title'].lower():
        print(b['id'], b['title'])
"
```

Replace `'keyword'` with the service or issue type you found.
