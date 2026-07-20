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

**Stack tools this reaches for**

| Present | This skill uses it for | Absent — what happens |
|---|---|---|
| **[metrics-query](../metrics-query/SKILL.md)** (Prometheus/Alertmanager) | steps 1, 2 and 4 — alerts, target health, capacity trends | the `curl`/`ssh` probes below. You lose history and get a point-in-time guess |
| **[quipu](../quipu/SKILL.md)** graph | "has this broken before, and what depends on it" before you touch anything | patrol on the raw finding alone; you will rediscover old incidents |
| **[notify](../notify/SKILL.md)** | delivering the patrol report | print it and say explicitly that it was not sent |
| **[bobbin](https://github.com/scbrown/bobbin)** | `bobbin search` when a finding points into a codebase you don't know | grep, slowly and blindly |
| **[graph-extract](../graph-extract/SKILL.md)** | writing a durable finding back to the graph | the finding lives in one terminal and dies there |

> **On tool names.** The `mcp__ops__*` calls below are an *example* ops MCP
> server. Any equivalent works, and the shell fallbacks beside them always work.
> The skill depends on the checks, not on a particular server.

> **On the `../metrics-query/promq.py` paths below.** Those resolve when the
> skills are installed side by side (`cp -r skein/skills/* ~/.claude/skills/`, or
> pointing your agent at `skein/skills/`). If you copied this skill alone, the
> raw `curl` beside every one of them is the whole check — nothing here needs
> the sibling script.

## Patrol Decision Tree

1. **Is something specifically broken?** (alert firing, user report, error)
   -> Targeted investigation. Check that service first.

2. **Routine health check?** (scheduled, "how's the fleet?")
   -> Full patrol. Follow the checklist below.

3. **Domain-specific?** (you own one area)
   -> Read the role-scoped reference for your domain.

## Full Patrol Checklist

### Step 1: Active Alerts

Preferred — [metrics-query](../metrics-query/SKILL.md), which excludes silenced
and inhibited alerts by default and tells you it did:

```bash
python3 ../metrics-query/promq.py alerts
python3 ../metrics-query/promq.py alerts --include-silenced   # read this too
```

Raw fallback:

```bash
curl -s "${ALERTMANAGER_URL}/api/v2/alerts?active=true&silenced=false&inhibited=false" \
  | jq '.[].labels.alertname'
# or: mcp__ops__alertmanager_query  query_type="alerts"
```

**Pass those query parameters explicitly.** Alertmanager's v2 API defaults
`silenced` and `inhibited` to *true*, so the obvious `curl .../api/v2/alerts`
counts alerts someone muted months ago as live incidents. And read the silenced
list at least once per patrol — a silence that has outlived its reason is an
alert you have decided not to see.

### Step 2: Scrape Targets

```bash
python3 ../metrics-query/promq.py query 'up == 0'   # exit 2 = EMPTY, not "healthy"
python3 ../metrics-query/promq.py targets           # what discovery actually knows about
```

Raw fallback:

```bash
curl -sG "${PROM_URL}/api/v1/query" --data-urlencode 'query=up == 0'
# or: mcp__ops__prometheus_query  query="up == 0"
```

Any target returning `up == 0` is unreachable. Cross-reference with known
issues in your tracker before filing new ones.

**Two things `up == 0` cannot tell you, and both read as good news:**

- **An empty result is not health.** No rows is also what a misspelled metric
  returns — over HTTP 200. Confirm the series exists (`query 'up'`) before you
  report green.
- **A target dropped from service discovery has no `up` series at all.** It
  cannot appear as down, because it cannot appear. Compare `targets` against your
  own expected inventory — kept in your IaC repo, not in your head.

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
python3 ../notify/notify.py -s warning -t "patrol" --file /tmp/patrol.md
```

Write the body to a **file** rather than an inline double-quoted string. A report
containing backticks or `$(...)` — and patrol reports quote commands constantly —
gets expanded by your shell before the tool ever sees it. That failure is silent:
the text either executes or is deleted, and the remaining sentence still scans.

**Check the notifier's exit code before you write "reported" anywhere.**
[notify](../notify/SKILL.md) exits `3` when no transport is configured — nothing
was sent. A patrol that ends "report delivered" off an unchecked exit status has
replaced one unverified claim with another, which is the exact thing this skill
is against.

## Feed what you learned back

A finding that lives only in a terminal is a finding the next patrol repeats.

- **Before touching a service**, ask the graph what depends on it —
  [quipu](../quipu/SKILL.md), step 5 (blast radius), and read its Limit (a) first.
- **After a real finding**, write it back with
  [graph-extract](../graph-extract/SKILL.md) so the next agent finds it by
  searching rather than by breaking the same thing again.
- **If the finding points into code you don't know**, `bobbin search "<symptom>"`
  and `hank impact <symbol>` beat grepping a repo you have never read. See
  [homelab-deploy](../homelab-deploy/SKILL.md) for the blast-radius pattern.

## Anti-Patterns

- Running a patrol without querying live data (relying on memory)
- Filing duplicate issues for known problems (check first)
- Fixing things during patrol without recording them (undocumented fixes)
- Skipping the IaC update after fixing something on a host
- **Reporting a check as green when it has never been able to go red.** If a check
  has never returned a failure, you have not verified it works — you have verified
  nothing. Force it red once.
