---
name: metrics-query
description: >-
  Ask Prometheus and Alertmanager what is actually happening, and tell an empty
  answer apart from a healthy one. Use this skill when asked "what's firing",
  "is anything down", "check the metrics", "query prometheus", "what alerts are
  active", "is the target up", "show me disk/CPU/memory over time", or when a
  patrol or a deploy needs live numbers rather than a dashboard someone
  remembers. Covers PromQL instant and range queries, scrape-target health, and
  Alertmanager alert triage including silenced/inhibited alerts.
  Portable: shell + HTTP to ${PROM_URL} / ${ALERTMANAGER_URL}, plus a stdlib
  Python engine. No exporter, no agent, no framework.
allowed-tools:
  - Bash
  - Read
---

# metrics-query — the numbers, and whether you may believe them

**Stack tools this reaches for**

| Present | This skill uses it for | Absent — what happens |
|---|---|---|
| **Prometheus** (`${PROM_URL}`) | every PromQL query, scrape-target health | the skill answers **nothing** and says so. It does not guess from `df`/`systemctl` and call that metrics — see [homelab-patrol](../homelab-patrol/SKILL.md) for the shell-probe path |
| **Alertmanager** (`${ALERTMANAGER_URL}`) | what is firing, what is silenced | `alerts` reports UNREACH; Prometheus' own `/api/v1/alerts` still shows *pending/firing rules*, but not silences |
| **[Quipu](https://github.com/scbrown/quipu)** graph | naming the thing an alert is about, before you touch it | skip it; you lose the "this broke before" context, nothing else |
| **[skein notify](../notify/SKILL.md)** | pushing a finding to a human | print the finding and say it was not sent |

Prometheus and Alertmanager are the only hard dependencies, they are public OSS
with stable documented HTTP APIs, and nothing here is specific to one deployment.

The engine is `promq.py` (stdlib + `urllib` only). Use it, or `curl` the same
endpoints by hand — the traps below apply either way.

## The one rule that matters

**An empty result is not a healthy result.** This is the whole reason the script
exists. Prometheus answers a query that matched nothing with **HTTP 200** and:

```json
{"status":"success","data":{"resultType":"vector","result":[]}}
```

That is byte-for-byte the shape of good news. It is also what you get when you
misspelled the metric, when the label selector has a typo, when the exporter was
never scraped, and when the target was quietly dropped from service discovery.
A client that does `data["result"]` and reports "0 down, all clear" cannot tell
any of those from the real thing.

So `promq.py` gives the empty case **its own exit code**:

| exit | meaning |
|---:|---|
| `0` | **OK** — succeeded and matched at least one series |
| `2` | **EMPTY** — succeeded and matched *nothing*. Not an error. **Not health.** |
| `1` | **ERROR** — the API said `status=error`, or returned non-2xx |
| `3` | **UNREACH** — the endpoint wasn't there, or wasn't configured |

Four outcomes, four codes, no rounding up. `EMPTY` and `UNREACH` are the two a
careless client silently converts into "fine".

## Step 1 — is anything down?

```text
$ python3 promq.py query 'up == 0'
EMPTY    query succeeded and matched 0 series: up == 0
         This is NOT the same as healthy. Before reporting green, run the
         selector bare (drop the comparison) and confirm the series exists.
$ echo $?
2
```

Do exactly what it says — drop the comparison and confirm the series is even
there:

```text
$ python3 promq.py query 'up'
               1  up{instance="host-a:9100",job="node"}
               1  up{instance="host-b:9100",job="node"}
$ echo $?
0
```

Two targets exist and both report up. *Now* `up == 0` returning nothing means
something. Had `up` itself come back EMPTY, the finding would not be "everything
is healthy", it would be "Prometheus is not scraping anything I asked about".

## Step 2 — the target that cannot appear as down

`up == 0` only covers targets Prometheus currently knows about. A target removed
from service discovery has **no `up` series at all** — it cannot report down,
because it cannot report. Ask the target list, and compare it to your own
inventory:

```text
$ python3 promq.py targets
down     blackbox/gateway   lastError=context deadline exceeded

3 active target(s), 1 not up.
NOTE: this lists targets service discovery CURRENTLY knows about. A target
      that was dropped from discovery is absent here and absent from `up` —
      it cannot appear as down because it cannot appear at all. Compare this
      list against your own inventory; the endpoint cannot do it for you.
```

`--all` lists healthy targets too. The comparison against inventory is the part
no endpoint can do for you — keep the expected target list in your IaC repo, not
in your head. For the absent-series case PromQL also offers `absent(up{job="x"})`,
which returns a series *when the selector matches nothing* — the inverse test,
and the only one that fires on silence.

## Step 3 — what is actually firing

Alertmanager's `/api/v2/alerts` defaults `silenced`, `inhibited` and
`unprocessed` to **true**. Inherit that default and you will report an alert
someone muted last month as a live incident. `promq.py alerts` asks explicitly,
excludes them by default, and prints which choice it made:

```text
$ python3 promq.py alerts
warning  active      DiskWillFillIn4Hours  host-b:9100

1 alert(s) [silenced EXCLUDED, inhibited EXCLUDED]
```

```text
$ python3 promq.py alerts --include-silenced
warning  active      DiskWillFillIn4Hours  host-b:9100
warning  suppressed  CertExpiringSoon  gateway
info     suppressed  NodeClockSkew  host-a:9100

3 alert(s) [silenced included, inhibited EXCLUDED]
```

One firing, three total. Both numbers are true; a report that gives one without
saying which is not. **Read the silenced list at least once per patrol** — a
silence that has outlived its reason is an alert you have decided not to see,
and it looks identical to an alert that never fires.

## Step 4 — history, when "is it bad now" isn't the question

```bash
python3 promq.py query 'node_filesystem_avail_ratio' --start now-6h --step 5m
```

Range queries hit `/api/v1/query_range` and print the latest value plus the
sample count, so a suspiciously short series is visible rather than averaged
away.

## The traps, in the order they bite

- **A 4xx parses as JSON too.** A bad query returns `{"status":"error",...}` with
  HTTP 422 — and a client reaching straight for `data.result` gets `[]` from it,
  landing on the same false "all clear" as a genuine empty. Check `.status`
  first, always. (This is the same failure shape as a swallowed graph 400; see
  the [quipu](../quipu/SKILL.md) skill's Limit (e). It recurs because every
  honest API reports errors in a field careless clients don't read.)
  ```text
  $ python3 promq.py query 'up{'
  ERROR    HTTP 422 bad_data: 1:3: parse error: unexpected end of input inside braces
  $ echo $?
  1
  ```
- **An instant query is up to five minutes stale.** Prometheus resolves an
  instant query against the last sample within its lookback window (5m by
  default). A target that died four minutes ago still reports its final `up 1`.
  If the question is "is it up *right now*", read `lastScrape`/`health` from
  `targets`, not `up` from a query.
- **`rate()` needs at least two samples inside the window.** A window shorter
  than ~4× the scrape interval silently yields no series — which arrives as
  EMPTY, which reads as zero traffic. Widen the window before you conclude
  anything is idle.
- **Counting alerts is not counting incidents.** One broken host with five rules
  attached is five alerts. Group by `alertname`/`instance` before you put a
  number in a report.
- **`up == 1` says the exporter answered, not that the service works.** `up` is a
  fact about the scrape, not about the thing being scraped. A wedged app with a
  live `/metrics` endpoint scrapes perfectly.

## Prove it can fail

A check that has never returned red isn't a check. Every outcome — including the
two that look like good news — is exercised in `test_promq.py`:

```bash
python3 -m unittest    # in this skill's directory
```

To see each for real, against your own endpoint:

| Outcome | How to force it |
|---|---|
| `EMPTY` (2) | `promq.py query 'up{job="no-such-job"}'` |
| `ERROR` (1) | `promq.py query 'up{'` — an unterminated selector |
| `UNREACH` (3) | `PROM_URL=http://127.0.0.1:1 promq.py query up` |
| `OK` (0) | `promq.py query 'up'` |

If `EMPTY` and `OK` produce the same exit code in your wrapper, your wrapper is
the bug.

## Configure (config, not constants)

```bash
export PROM_URL=http://prometheus.example.com:9090      # required for query/targets
export ALERTMANAGER_URL=http://alerts.example.com:9093  # required for alerts
export PROM_BEARER_TOKEN=...                            # optional: sent as Authorization: Bearer
export PROM_TIMEOUT=10                                  # seconds
```

Nothing is hardcoded. If either URL is unset, the affected subcommand exits `3`
and reports that **nothing was queried** — it never falls back to a cheerful
silence.

## Where the findings go

- A real finding belongs in your tracker, not only in a terminal.
- Push it to a human with [notify](../notify/SKILL.md) — and read that skill's
  first principle before you claim anyone was told.
- Durable facts ("this host's disk fills every Tuesday") belong in the graph via
  [graph-extract](../graph-extract/SKILL.md), so the next agent finds them with
  [quipu](../quipu/SKILL.md) instead of rediscovering them.
- Ship *queries*, not remembered numbers. Every figure here moves hourly.
