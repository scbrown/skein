<p align="center">
  <img src="assets/logo.svg" width="200" alt="skein logo — threads twisted into a bundle and tied with a band"/>
</p>

<h1 align="center">skein</h1>

<p align="center">
  <em>🧵 The skills layer for a local-first agent stack</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <img src="https://img.shields.io/badge/skills-11-E39A4E.svg" alt="11 skills"/>
  <img src="https://img.shields.io/badge/skein_runtime-none-3E9E9A.svg" alt="skein ships no runtime"/>
  <img src="https://img.shields.io/badge/install-copy%20a%20directory-8C98A8.svg" alt="Install is copying a directory"/>
  <img src="https://img.shields.io/badge/drives-bobbin%20·%20quipu%20·%20hank%20·%20st-6C7A89.svg" alt="Drives bobbin, quipu, hank, shantytown"/>
  <img src="https://img.shields.io/badge/agents-any%20SKILL.md-lightgrey.svg" alt="Works with any agent that reads SKILL.md"/>
</p>

> *A skein is a bundle of threads, tied so it can be carried. Pull one out when you need it.* 🧶

**Skills for LLM coding agents** — Claude Code, Codex, Cursor, Gemini CLI, and anything else that
reads a `SKILL.md`. Each skill **drives a real tool when that tool is there, and says exactly what
it cannot do when it isn't.**

> **Portability is a property. Integration is the pitch.**
>
> skein itself ships no runtime, no daemon, and no dependencies — a skill is markdown plus, at most,
> a stdlib Python script, and installing one is `cp -r`. That is the *property*. But a skills layer
> that drives nothing is a style guide. **Five of the eleven skills want a service**: three need a
> [Quipu](https://github.com/scbrown/quipu) graph endpoint, one needs Prometheus, one needs a push
> server. That is not a hidden cost — it is the point, and every skill states its dependency and its
> degradation in a table at the top of the file.

## 🧱 The stack

skein is one layer of a local-first agent stack. Every other piece is a separate, public, standalone
tool; skein is how an agent actually drives them.

```text
                    ┌──────────────────────────────────────┐
                    │     your agent (any SKILL.md)        │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │   skein — the skills layer           │   ← this repo
                    │   how to drive the row below         │
                    └──┬─────────┬─────────┬─────────┬─────┘
                       │         │         │         │
               ┌───────▼──┐ ┌────▼────┐ ┌──▼───┐ ┌───▼────────┐
               │  bobbin  │ │  quipu  │ │ hank │ │ shantytown │
               │   code   │ │ memory  │ │struct│ │  the crew  │
               └───────┬──┘ └────┬────┘ └──┬───┘ └───┬────────┘
                       │         │         │         │
                    ┌──▼─────────▼─────────▼─────────▼─────┐
                    │  shanty — the terminal you watch it  │
                    │  all happen in                       │
                    └──────────────────────────────────────┘
```

| tool | what it is | the question it answers | skills that drive it |
|---|---|---|---|
| **[bobbin](https://github.com/scbrown/bobbin)** | code search + git coupling | *what does this code say?* | homelab-deploy · homelab-patrol · planning-with-files · dispatch-work |
| **[quipu](https://github.com/scbrown/quipu)** | RDF/SPARQL knowledge graph | *what do we already know?* | **quipu · graph-extract · graph-report** |
| **[hank](https://github.com/scbrown/hank)** | code structure + policy guards | *what will this break?* | homelab-deploy · planning-with-files · quipu |
| **[shantytown](https://github.com/scbrown/shantytown)** | agent crew harness (`st`) | *who does the work?* | **dispatch-work** |
| **[shanty](https://github.com/scbrown/shanty)** | tmux wrapper + status bar | *where you watch it* | — |
| **skein** | *this repo* | *how an agent drives all of it* | — |
| [Prometheus](https://prometheus.io) / [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) | metrics + alerting | *what is happening right now?* | **metrics-query** · homelab-patrol · homelab-deploy |
| [ntfy](https://ntfy.sh) / any JSON webhook | push notification | *how a human finds out* | **notify** · homelab-patrol |

Skills in **bold** *require* that tool — they have no offline mode and will say so rather than
invent one. Everything else is an accelerant with a documented fallback.

**On [Gas Town](https://github.com/gastownhall/gastown).** Gas Town is the heavyweight multi-agent
workspace manager in this space — session lifecycle, work routing, scheduling, the whole town. We
run a fleet on it. skein does not replace it and is not trying to: `dispatch-work` distils *one*
capability out of that shape into something you can carry onto a machine that has never heard of a
workspace manager. Reach for Gas Town when you want the whole workshop.

## 🖥️ See It In Action

**An empty answer is not a healthy one.** The most common false "all clear" in monitoring, given its
own exit code:

```text
$ python3 promq.py query 'up == 0'
EMPTY    query succeeded and matched 0 series: up == 0
         This is NOT the same as healthy. Before reporting green, run the
         selector bare (drop the comparison) and confirm the series exists.
$ echo $?
2
```

Prometheus answers a query that matched nothing with **HTTP 200** and an empty result — byte-for-byte
the shape of good news, and also exactly what a misspelled metric returns. So `metrics-query`
separates `EMPTY` (2) from `OK` (0), and you do what it says:

```text
$ python3 promq.py query 'up'
               1  up{instance="host-a:9100",job="node"}
               1  up{instance="host-b:9100",job="node"}
$ echo $?
0
```

*Now* `up == 0` returning nothing means something.

**Handing work to another agent — and knowing it landed.**

```text
$ python3 dispatch.py create "Fix the ingress 502s" --backend gh
#128

$ python3 dispatch.py send harding:0.0 '#128'
REFUSE   in-flight work
         inputs: marker='esc to interrupt' pane='harding:0.0'
refused: pane not ready (refuse); nothing sent
$ echo $?
3
```

It refused to interrupt a working agent, and it showed you the input it judged on. Exit `0` means
*delivered and confirmed*; exit `2` means sent-but-unconfirmed — record nothing and re-dispatch,
because a tracker full of work nobody was told about is worse than a dropped message.

That is the portable fallback. **With [shantytown](https://github.com/scbrown/shantytown) installed,
`st go <item> <agent>` is the first-class path** — it makes the same judgement on the same evidence,
plus two refusals a standalone script cannot make: it knows who the agents are (`st crew`), and it
refuses to silently steal an item another agent already holds.

**Nobody was told, and the tool says so.**

```text
$ python3 notify.py "disk 92% on host-b"
NOTHING WAS SENT — no transport is configured.
  Set NTFY_URL + NTFY_TOPIC, and/or NOTIFY_WEBHOOK_URL.
  This is exit 3, never 0: an escalation path with no transport behind it
  is not a quiet success, it is the outage you find out about tomorrow.
$ echo $?
3
```

**Asking the graph before you touch a service.**

```text
$ curl -s $GRAPH_URL/search -X POST -H 'Content-Type: application/json' \
    -d '{"query":"database server"}'
{"count":10,"results":[{"entity":"http://example.org/ontology/db-server.service",
 "score":0.647,
 "text":"db-server.service. SQL server on db.example.com:3306, the data plane. Fragile;
 a downstream service previously died for nine weeks via systemd stop-propagation from
 this unit.","valid_from":"2026-05-02T11:31:08Z"}]}
```

That `text` is often the whole answer — and it is the sentence that stops you from running
`systemctl stop db-server.service` at 11pm. The skill then makes you widen before you trust it:

```text
$ # step 3 — find EVERY node for one real thing, before any traversal
$ curl -s $GRAPH_URL/query -X POST -H 'Content-Type: application/json' \
    -d '{"query":"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?s ?l WHERE
         { ?s rdfs:label ?l . FILTER(regex(?l, \"db\", \"i\")) } LIMIT 20"}'
{"count":7,"rows":[{"s":"...db"},{"s":"...Db"},{"s":"...db.example.com"},
 {"s":"...db-server"},{"s":"...db-server.service"},{"s":"...app-db"},{"s":"...local-db-fork"}]}
```

Seven nodes, one database. A blast-radius query against any *one* of them returns a subset that
looks exactly like a complete answer — which is worse than an error, because an error tells you it
failed.

## Why this exists

Most agent tooling assumes you're writing software. Almost none of it assumes you're **running
infrastructure** — deploying to hosts you own, patrolling machines that drift, and remembering what
broke six weeks ago. These are the skills an operator actually reaches for.

They came out of a live multi-agent homelab, so they encode things you only learn by being wrong:
patrol before you trust a dashboard, query the graph before you name an entity, and never let a
check report success it hasn't earned.

## 🤔 Why Skein?

|  | **Hand-rolled prompts** | **MCP servers** | **LangChain-style frameworks** | **Agent plugin systems** | **[Gas Town](https://github.com/gastownhall/gastown)** | **skein** |
|--|:---:|:---:|:---:|:---:|:---:|:---:|
| Agent-agnostic (no vendor format)     | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| No server or daemon **of its own**    | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Install = copy a directory            | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Version-controlled and diffable       | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| No language/runtime dependency        | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| States its degradation per capability | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Typed tool contract & auto-discovery  | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Multi-agent orchestration & lifecycle | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |

The last two rows are the honest ones. **skein is not an orchestrator and does not want to be.**

An MCP server is the closest comparison, and the difference is worth stating plainly: an MCP tool is
a capability welded to a runtime and a host. A skill is the same capability *written down*, so it
runs from any agent, on any machine, with a shell. Several skills here were generalised out of a
private MCP server for exactly that reason — [`docs/proposed-skills.md`](docs/proposed-skills.md)
records which ones survived the translation, and which were rejected for failing it.

Requirements in full: `curl`, `tmux` (dispatch only), and Python 3 standard library. No packages, no
lockfile, no build step.

## 🧵 The Skills

| skill | what it does | needs | without it |
|---|---|---|---|
| 📮 **dispatch-work** | Hand a work item to another agent — check the pane is ready, send, verify it landed. Refuses to interrupt a busy agent. | `tmux`; `st` preferred | bundled stdlib engine over plain tmux |
| 📈 **metrics-query** | PromQL queries, scrape-target health, alert triage — with an empty result reported as its own outcome, not as good news. | **Prometheus** / Alertmanager | **nothing.** Exits `3` and says it queried nothing |
| 📣 **notify** | Push a finding to a human via ntfy or a JSON webhook, reporting per-transport acceptance. | **ntfy or a webhook** | **nothing.** Exits `3`: "NOTHING WAS SENT" |
| 🚀 **homelab-deploy** | Deploy services — binaries, configs, IaC, rollback. IaC-first, verify-after. | — | full shell path; `hank`/`bobbin` sharpen blast radius |
| 🩺 **homelab-patrol** | Health checks across a fleet. "What's broken?" — from live data, never memory. | — | full shell path; Prometheus adds history |
| 🔎 **quipu** | Query the graph before you act — and what the graph is *not* to be trusted about. | **Quipu endpoint** | **nothing.** No offline mode, by design |
| 🧬 **graph-extract** | Extract entities and relationships from docs, code, and issues into the graph. | **Quipu endpoint** | **nothing.** Saves the payload; never claims a write |
| 🗺️ **graph-report** | Live orientation report — size, central entities, suggested questions. | **Quipu endpoint** | **nothing.** Names the sections it couldn't compute |
| 📋 **planning-with-files** | File-based planning that survives a context reset. | — | this one needs nothing at all |
| 🚦 **deciding-when-to-ask** | Handle it yourself or bubble it up? Gate on reversibility / blast radius, route by type, batch approvals, tier by burn — so a coordinator only surfaces genuine human calls. | — | pure judgment discipline; a tracker/notify sharpen where escalations land |
| 🪞 **session-retro** | A Stop hook that, once per session, harvests session friction into filed improvement issues. Fires once, not every turn; fails open. | — | files to a tracker if present, else a markdown backlog |

## ✨ Features

🧵 **Portable by construction** — A skill is a `SKILL.md` and, at most, a stdlib Python script. There
is no plugin API to target, so there is nothing to port when you change agents.

🔌 **Zero install** — `cp -r skills/<skill> ~/.claude/skills/`. That's the whole procedure. No
package manager, no lockfile, no build, no daemon to keep alive.

🔗 **Reaches for the better tool first** — where a real tool does the job properly, the skill drives
it: `st` for dispatch, `bobbin` for search, `hank` for blast radius, Quipu for memory, Prometheus
for history. Where it isn't installed, the skill takes the documented fallback — or refuses, and
says which.

📉 **States its own degradation** — every skill opens with a table of what it uses and what happens
without it. No skill silently substitutes a worse answer for the one you asked for.

⚙️ **Config, not constants** — Every target is an environment variable (`GRAPH_URL`, `PROM_URL`,
`NTFY_URL`, `DISPATCH_*`). A skill that hardcodes a hostname is ours, not yours — and we treat one
that slips through as a bug.

🧪 **Checks that can fail** — Every skill that verifies something documents how to *make it fail*.
`dispatch-work`, `metrics-query` and `notify` ship unit tests that exercise **every** outcome,
including the ones that look like good news. A health check that has never returned red is not a
check.

🚦 **Honest exit codes** — Scripts branch without parsing prose. `promq.py`: `0` matched · `2`
matched nothing · `1` API error · `3` unreachable. `notify.py`: `0` all accepted · `1` partial ·
`2` all failed · `3` **nothing was sent**. Ambiguity is a bug, not a nuance.

🧠 **Encodes the caveat, not just the API** — The `quipu` skill spends as much space on what the
graph will *lie* to you about (unresolved duplicate entities, SHACL validating nothing, a swallowed
HTTP 400 that reads as "0 results, all clean") as on how to query it. `metrics-query` does the same
for a 422 that parses cleanly, and for the target that cannot appear as down because it was dropped
from service discovery.

📋 **Survives a context reset** — `planning-with-files` keeps the plan, findings, and progress on
disk, so a cleared session picks up where the last one stopped.

## ⚙️ Configure

Skills read their targets from the environment. Nothing is hardcoded — see
[`.env.example`](.env.example) for the annotated version.

| variable | used by | required? |
|---|---|---|
| `GRAPH_URL` | quipu · graph-extract · graph-report | **yes**, for those three |
| `GRAPH_GROUP` | graph-extract | yes, to write |
| `GRAPH_NS` | quipu · graph-extract | yes |
| `PROM_URL` | metrics-query · homelab-patrol · homelab-deploy | **yes**, for `query` / `targets` |
| `ALERTMANAGER_URL` | metrics-query · homelab-patrol | **yes**, for `alerts` |
| `PROM_BEARER_TOKEN`, `PROM_TIMEOUT` | metrics-query | no |
| `NTFY_URL` + `NTFY_TOPIC` | notify | **both or neither** — half is not a transport |
| `NTFY_TOKEN` | notify | no |
| `NOTIFY_WEBHOOK_URL` | notify | one transport is required — this or ntfy |
| `NOTIFY_WEBHOOK_KEY` | notify | no — `text` (Slack/Mattermost) or `content` (Discord) |
| `NOTIFY_MIN_SEVERITY`, `NOTIFY_PRIORITY_*`, `NOTIFY_TIMEOUT` | notify | no |
| `SEARCH_URL` | homelab-patrol | no — remote bobbin |
| `DB_HOST`, `BEADS_DB` | examples in quipu / patrol | no |
| `DISPATCH_*` | dispatch-work fallback engine | no — `st` carries its own config |

## 📦 Install

```bash
git clone https://github.com/scbrown/skein
cp -r skein/skills/<skill> ~/.claude/skills/
```

Or point your agent's skill path straight at `skein/skills/`.

## Conventions

- **Python, not bash**, for anything that makes a decision or parses JSON.
- **A check must be able to fail.** If a health check has never returned red, it isn't a check.
  Every skill that verifies something says how to prove it can fail.
- **Config, not constants.** A skill that hardcodes a hostname is ours, not yours.
- **Reach for the real tool first, fall back second, and name which one you took.** A skill that
  quietly degrades has told you nothing about the quality of its answer.
- **Never report success you have not earned.** Not delivered, not verified, not queried — say so.
  Every exit code in this repo exists to stop one of those distinctions from collapsing into `0`.

## Status

Early. Extracted from a working homelab, generalised, and published with the intent of being useful
to someone who isn't us. If a skill leaks an assumption about our environment, that's a bug — open
an issue. Skills under consideration, and the ones deliberately rejected, are in
[`docs/proposed-skills.md`](docs/proposed-skills.md).

## License

[MIT](LICENSE)
