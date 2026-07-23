# Proposed skills

A working list of capabilities worth turning into skein skills, why each is (or
isn't) worth shipping, and what it degrades to when the thing it drives isn't
there.

The candidates were generalised from an ops MCP server's tool surface. **skein
does not require that MCP server, or any MCP server** — an MCP tool is a
capability locked to one runtime and one host; a skill is the same capability
written down so anything with a shell can run it. So the test each candidate has
to pass is not "is this useful?" but:

> **Does it survive being written as shell + HTTP against a public, documented
> API — and is what's left still worth a page?**

Several do not, and saying so is the point of this file.

## Status

| Skill | Status | Depends on |
|---|---|---|
| [metrics-query](../skills/metrics-query/SKILL.md) | **shipped** | Prometheus, Alertmanager |
| [notify](../skills/notify/SKILL.md) | **shipped** | ntfy and/or a JSON webhook |
| ci-watch | proposed | Forgejo/Gitea or GitHub Actions |
| cert-check | proposed | shell (`openssl`) |
| container-triage | proposed, with reservations | docker/podman/systemd |
| probe | proposed, low priority | shell (`curl`, `dig`) |
| backup-verify | **rejected** — see below | — |
| queue-depth | **rejected** — see below | — |

---

## Shipped

### metrics-query

**What it does.** PromQL instant and range queries, scrape-target health, and
Alertmanager alert triage — with an empty result reported as its own outcome
rather than as good news.

**Env.** `PROM_URL`, `ALERTMANAGER_URL`, `PROM_BEARER_TOKEN` (optional),
`PROM_TIMEOUT`.

**Degrades to.** Nothing, deliberately. Without Prometheus it exits `3` and says
it queried nothing. It does **not** fall back to `df`/`systemctl` and call that
metrics — that is `homelab-patrol`'s job, and blurring the two is how a fleet
ends up believing it has monitoring it doesn't have.

**Why ship it.** Generalises `prometheus_query` + `alertmanager_query` with zero
loss: both are public OSS with stable versioned HTTP APIs (`/api/v1`, `/api/v2`)
that thousands of people already run. And the capability that's genuinely hard to
carry in your head — not the curl, but *the traps* — is real and transferable:
an empty vector is a 200; a 422 also parses; instant queries are up to 5 minutes
stale; `/api/v2/alerts` includes silenced alerts by default; a target dropped
from service discovery cannot appear as down.

### notify

**What it does.** Pushes a message via ntfy and/or a generic JSON webhook, with
severity routing, and reports per-transport acceptance — never a blanket "sent".

**Env.** `NTFY_URL`, `NTFY_TOPIC`, `NTFY_TOKEN`, `NOTIFY_WEBHOOK_URL`,
`NOTIFY_WEBHOOK_KEY`, `NOTIFY_MIN_SEVERITY`, `NOTIFY_PRIORITY_*`,
`NOTIFY_TIMEOUT`.

**Degrades to.** Exit `3` and an explicit "NOTHING WAS SENT". Never a silent
no-op.

**Why ship it.** This merges `ntfy_publish` and `irc_send`, as suggested — they
are one capability ("get a sentence in front of a person"), and two thin skills
would be two pages of duplicated caveats. The transport is trivial; the *ethic*
is the deliverable, and it is this repo's own: an escalation path with no
transport behind it reports success forever, and is indistinguishable from a
working one until the night it matters.

**Where I diverged.** IRC gets no client. IRC needs a persistent connection,
a persistent connection is a daemon, and skein does not ship daemons. Pointing
`NOTIFY_WEBHOOK_URL` at a bridge is the honest generalisation; shipping a
half-alive IRC client would violate the repo's central claim to save one config
line.

---

## Proposed

### ci-watch

**What it does.** Answer "did my push pass?" against a self-hosted forge *and*
GitHub with one decision tree: list recent runs for a ref, find the failing job,
pull only the failing step's log tail, and wait for an in-flight run to settle.

**Env.** `CI_KIND` (`forgejo`|`github`), `CI_URL`, `CI_REPO`, `CI_TOKEN`.

**Degrades to.** On GitHub, `gh run list/view/watch` if the CLI is present (it
is better than anything this skill would write). Without a token: nothing —
CI APIs are authenticated, and there is no read-only guess to fall back on.

**Why it's worth shipping.** Forgejo/Gitea implement a Gitea-compatible Actions
API that is genuinely close to GitHub's shape (runs → jobs → logs), so one
decision tree really does cover both, and the *agent-facing* discipline is the
same on either: **do not paste a 4MB job log into context.** Fetch the run, find
the failed job, and read the last ~100 lines of the failing step only. That rule
is the skill.

**Why it isn't shipped yet.** Half of the likely readership has `gh`, which
already does this well, so the value concentrates on the Forgejo side — and the
Forgejo Actions API surface is version-sensitive in a way Prometheus' is not.
Shipping it means pinning versions I have verified against, and I would rather
propose it accurately than ship it vaguely. It is the strongest of the remaining
candidates.

### cert-check

**What it does.** Days-until-expiry for a list of TLS endpoints, plus the two
findings a naive check misses: a chain that is expired at an *intermediate*, and
a name mismatch on a host that is otherwise perfectly valid.

**Env.** `CERT_TARGETS` (comma-separated `host:port`), `CERT_WARN_DAYS`.

**Degrades to.** Nothing needed — it is `openssl s_client` and date arithmetic.
Pure shell, no service at all, which makes it the most portable thing on this
list.

**Why it's worth shipping.** Certificate expiry is the canonical silent failure:
everything is green, and then at 03:00 on a Sunday nothing is. It is small,
completely verifiable, and it fails loudly by construction. It also pairs
naturally with `notify` for the warn-at-14-days path.

**Why it isn't shipped yet.** Only because it is *small* — it may honestly be
one section of `homelab-patrol` rather than a skill of its own, and I did not
want to inflate the skill count to make a page look busier. Worth a decision
before implementation, not after.

### container-triage — with reservations

**What it does.** "What's running, what's unhealthy, why did it restart" over
docker/podman/systemd behind one vocabulary.

**Env.** `CONTAINER_RUNTIME` (`docker`|`podman`|`nerdctl`), `CONTAINER_HOST`.

**Degrades to.** `systemctl` + `journalctl` when there is no container runtime.

**Why I am hesitant, and why I think the original grouping is the weakest of the
four.** This bundles `list_containers`, `container_status`, `container_logs`,
`container_metrics`, `service_health`, and `service_restart` — six tools, and the
generalisation is not as clean as it looks:

- **It overlaps two existing skills.** `homelab-patrol` already covers service
  health and log inspection; `homelab-deploy` already covers pre/post-deploy
  state and restart. A third skill in the same territory means three places to
  keep a rule consistent, and rules that drift between skills are worse than a
  rule in one slightly-wrong place.
- **The runtimes are not actually the same shape.** `docker ps` and `podman ps`
  agree; health checks, restart policies, log drivers, and rootless namespaces do
  not. A skill that papers over that will be confidently wrong on the half of
  cases where it matters — which is exactly the failure this repo is written
  against.
- **`service_restart` is a write, and it does not belong in a triage skill.**
  Bundling "show me the logs" with "restart it" invites an agent to restart
  something because a log looked bad. Restart belongs with deploy, behind that
  skill's verify-after invariant.

**Recommendation:** don't build this as a skill. Fold container awareness into
`homelab-patrol` (read) and `homelab-deploy` (restart, with the existing
guardrails). Revisit only if a concrete question arrives that neither can answer.

### probe — low priority

**What it does.** Batch reachability: HTTP status/latency for a list of URLs,
DNS resolution, TCP port checks. Generalises `batch_probe`, `network_check`,
`disk_usage`.

**Env.** `PROBE_TARGETS`.

**Degrades to.** It *is* the degraded path — `curl -o /dev/null -w`, `dig`, `df`.

**Why it's low priority.** These are the shell fallbacks `homelab-patrol`
already documents inline. Extracting them into a skill adds indirection without
adding knowledge: there is no hard-won trap here, just commands. The one idea
worth keeping — *check from where the user is, not from the host that serves it*
— is a sentence, and it belongs in `homelab-patrol`.

I'd also push back on grouping `disk_usage` and `network_check` with Prometheus
and Alertmanager as one "observability cluster". They are different kinds of
thing: Prometheus is a queryable time-series API with real depth and real traps;
`df` is a command. Bundling them would have produced a skill whose good half
hides behind its trivial half.

---

## Rejected

### backup-verify (`backup_status`)

The *idea* is the best one on the whole list — "a backup you have never restored
is not a backup" is exactly this repo's ethic, and an untested backup is the most
expensive silent success in operations.

But there is no public API to generalise against. Every deployment's backup
status lives somewhere different: restic, borg, ZFS snapshots, a Proxmox job
table, a cron log. A skill would either hardcode one tool (not portable) or
reduce to "check your backups" (not a skill). **Rejected as a skill; the sentence
belongs in `homelab-patrol`'s checklist**, where it costs nothing and still gets
read.

### queue-depth (`queue_depth`)

Too site-specific. "The queue" is a different thing in every deployment, and once
you have generalised it far enough to be portable, it is a Prometheus query —
which `metrics-query` already does, better, with the staleness caveat attached.

---

## The pattern in what got rejected

Three of these failed the same test in three different ways, and it is worth
naming because it will come up again:

- **backup-verify** — a great rule with no public API behind it. The rule
  survives; the skill does not.
- **probe** — a real API, but no hard-won knowledge to carry. Commands, not a
  capability.
- **container-triage** — both an API and knowledge, but the knowledge already
  lives in two other skills, and the runtimes differ exactly where it counts.

A skein skill has to be all three at once: **a stable public interface, a trap
worth writing down, and no other skill that already owns it.** Everything shipped
above clears that bar; everything rejected misses exactly one leg of it.
