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

A patrol is a structured health check. You gather live data, compare it to
expected state, and act on discrepancies. Never assume — always query.

> **On tool names.** The `mcp__ops__*` calls below are an *example* ops MCP
> server. Any equivalent works, and the shell fallbacks beside them always work.
> The skill depends on the checks, not on a particular server.

## Patrol Decision Tree

1. **Is something specifically broken?** (alert firing, user report, error)
   -> Targeted investigation. Check that service first.

2. **Routine health check?** (scheduled, "how's the fleet?")
   -> Full patrol. Follow the checklist below.

3. **Domain-specific?** (you own one area)
   -> Read the role-scoped reference for your domain.

## Full Patrol Checklist

### Step 1: Active Alerts

```bash
curl -s http://<alertmanager>:9093/api/v2/alerts | jq '.[].labels.alertname'
# or: mcp__ops__alertmanager_query  query_type="alerts"
```

Check for firing alerts. Silenced alerts are acknowledged — focus on unsilenced.

### Step 2: Scrape Targets

```bash
curl -sG http://<prometheus>:9090/api/v1/query --data-urlencode 'query=up == 0'
# or: mcp__ops__prometheus_query  query="up == 0"
```

Any target returning `up == 0` is unreachable. Cross-reference with known
issues in your tracker before filing new ones.

### Step 3: Key Services

Check critical services are running:

```bash
systemctl is-active <service>                  # on the host
ssh root@<host> systemctl is-active <service>  # remotely
# or: mcp__ops__service_health  host="${DB_HOST}" service="db-server"
```

Keep the list of "critical" services in your IaC repo, not in your head —
a check you have to remember to run is a check that stops running.

### Step 4: Disk Usage

```bash
ssh root@<host> df -h /
# or: mcp__ops__disk_usage  host="<host>"
```

Alert threshold: >85% warrants investigation, >95% is urgent.

### Step 5: Recent Work Activity

```bash
<tracker> list --status=in_progress   # What's being worked on?
<tracker> list --status=blocked       # What's stuck?
<tracker> ready                       # What's available?
```

## Role-Scoped Patrols

Different roles patrol different domains. Read the reference matching yours:

- **Infrastructure**: `references/infra-patrol.md`
  Services, alerts, capacity, host health
- **Comms**: `references/comms-patrol.md`
  Chat bridges, message routing, event delivery
- **Tooling**: `references/tooling-patrol.md`
  Git hygiene, CI status, CLI tools, MCP health
- **Search / context**: `references/bobbin-patrol.md`
  Index health, injection quality, feedback scores

If you don't own a specific domain, run the full checklist above.

## Acting on Findings

| Finding | Action |
|---------|--------|
| Alert firing, no issue exists | File an issue with details |
| Service down | Check logs, attempt restart, file an issue if recurring |
| Disk >90% | Identify growth source, clean if safe, file an issue |
| Stale in-progress item (>24h) | Comment asking for status |
| Blocked item with resolved dep | Update the dependency, unblock |

## Patrol Report

After a patrol, send a brief report to wherever your team actually reads things
(chat, an issue comment, a status page):

```bash
cat > /tmp/patrol.md <<'BODY'
Fleet: X alerts firing, Y services healthy
Issues found: (list or "none")
Filed: (IDs or "none")
BODY
<your-notify-command> --file /tmp/patrol.md
```

Write the body to a **file** rather than an inline double-quoted string. A report
containing backticks or `$(...)` — and patrol reports quote commands constantly —
gets expanded by your shell before the tool ever sees it. That failure is silent:
the text either executes or is deleted, and the remaining sentence still scans.

## Anti-Patterns

- Running a patrol without querying live data (relying on memory)
- Filing duplicate issues for known problems (check first)
- Fixing things during patrol without recording them (undocumented fixes)
- Skipping the IaC update after fixing something on a host
- **Reporting a check as green when it has never been able to go red.** If a check
  has never returned a failure, you have not verified it works — you have verified
  nothing. Force it red once.
