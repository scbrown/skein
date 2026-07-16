---
name: homelab-patrol
description: >
  Check homelab health and run diagnostics. Use this skill when asked to
  "patrol", "check health", "run diagnostics", "system status", "what's
  broken", "fleet check", or when investigating alerts, monitoring issues,
  or service health. Covers service checks, alert triage, metrics review,
  disk/capacity monitoring, and role-scoped domain patrols.
---

# Patrol Skill

A patrol is a structured health check. You gather live data, compare to
expected state, and act on discrepancies. Never assume — always query.

## Patrol Decision Tree

1. **Is something specifically broken?** (alert firing, user report, error)
   -> Targeted investigation. Check that service first.

2. **Routine health check?** (scheduled, "how's the fleet?")
   -> Full patrol. Follow the checklist below.

3. **Domain-specific?** (your keeper/ranger area)
   -> Read the role-scoped reference for your domain.

## Full Patrol Checklist

### Step 1: Active Alerts

```text
mcp__homelab__alertmanager_query  query_type="alerts"
```

Check for firing alerts. Silenced alerts are acknowledged — focus on unsilenced.

### Step 2: Scrape Targets

```text
mcp__homelab__prometheus_query  query="up == 0"
```

Any target returning `up == 0` is unreachable. Cross-reference with known
issues (check beads) before filing new ones.

### Step 3: Key Services

Check critical services are running:

```text
mcp__homelab__service_health  container="${DB_HOST}" service="dolt-server"
mcp__homelab__service_health  container="automation" service="homelab-mcp"
mcp__homelab__service_health  container="bot.lan" service="aegis-irc"
mcp__homelab__service_health  container="monitoring" service="prometheus"
```

### Step 4: Disk Usage

```text
mcp__homelab__disk_usage  container="tagi"
mcp__homelab__disk_usage  container="${DB_HOST}"
mcp__homelab__disk_usage  container="automation"
```

Alert threshold: >85% warrants investigation, >95% is urgent.

### Step 5: Recent Bead Activity

```bash
bd list --status=in_progress   # What's being worked on?
bd list --status=blocked       # What's stuck?
bd ready                       # What's available?
```

## Role-Scoped Patrols

Different roles patrol different domains. Check your role and read the
matching reference file:

- **Infrastructure** (wu, maldoon): `references/infra-patrol.md`
  Services, alerts, capacity, container health
- **Comms** (ellie): `references/comms-patrol.md`
  IRC, Telegram, message-router, reactor event delivery
- **Tooling** (arnold): `references/tooling-patrol.md`
  Git hygiene, CI status, CLI tools, MCP health
- **Search** (ian): `references/bobbin-patrol.md`
  Index health, injection quality, feedback scores

If you don't have a specific role, run the full checklist above.

## Acting on Findings

| Finding | Action |
|---------|--------|
| Alert firing, no bead exists | File a bead with details |
| Service down | Check logs, attempt restart, file bead if recurring |
| Disk >90% | Identify growth source, clean if safe, file bead |
| Stale in_progress bead (>24h) | Comment asking for status |
| Blocked bead with resolved dep | Update dependency, unblock |

## Patrol Report

After patrol, send a brief report:

```bash
gt mail send aegis/crew/goldblum -s "Patrol: <domain> status" --stdin <<'BODY'
Fleet: X alerts firing, Y services healthy
Issues found: (list or "none")
Beads filed: (IDs or "none")
BODY
```

## Anti-Patterns

- Running patrol without querying live data (relying on memory)
- Filing duplicate beads for known issues (check first)
- Fixing things during patrol without filing beads (undocumented fixes)
- Skipping IaC update after fixing something on a container
