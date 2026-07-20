<p align="center">
  <img src="assets/logo.svg" width="200" alt="skein logo — threads twisted into a bundle and tied with a band"/>
</p>

<h1 align="center">skein</h1>

<p align="center">
  <em>🧵 Portable agentic skills for running infrastructure</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <img src="https://img.shields.io/badge/skills-7-E39A4E.svg" alt="7 skills"/>
  <img src="https://img.shields.io/badge/runtime-none-3E9E9A.svg" alt="No runtime"/>
  <img src="https://img.shields.io/badge/requires-shell%20%2B%20HTTP-lightgrey.svg" alt="Requires shell and HTTP"/>
  <img src="https://img.shields.io/badge/agents-any%20SKILL.md-8C98A8.svg" alt="Works with any agent that reads SKILL.md"/>
</p>

> *A skein is a bundle of threads, tied so it can be carried. Pull one out when you need it.* 🧶

**Skills for LLM coding agents** — Claude Code, Codex, Cursor, Gemini CLI, and anything else that
reads a `SKILL.md`. They need **shell + HTTP and nothing else**: no framework, no runtime, no
service to operate. Copy a directory in and it works.

## Why this exists

Most agent tooling assumes you're writing software. Almost none of it assumes you're **running
infrastructure** — deploying to hosts you own, patrolling machines that drift, and remembering what
broke six weeks ago. These are the skills an operator actually reaches for.

They came out of a live multi-agent homelab, so they encode things you only learn by being wrong:
patrol before you trust a dashboard, query the graph before you name an entity, and never let a
check report success it hasn't earned.

## See It In Action

**Handing work to another agent — and knowing it landed.**

```text
$ python3 dispatch.py create "Fix the ingress 502s" --backend gh
#128

$ python3 dispatch.py triage harding:0.0 --hint "Fix the ingress 502s"
REFUSE   in-flight work
         inputs: marker='esc to interrupt' pane='harding:0.0'

$ python3 dispatch.py send harding:0.0 '#128'
REFUSE   in-flight work
         inputs: marker='esc to interrupt' pane='harding:0.0'
refused: pane not ready (refuse); nothing sent
$ echo $?
3
```

It refused to interrupt a working agent, and it showed you the input it judged on. A minute later:

```text
$ python3 dispatch.py send harding:0.0 '#128'
delivered #128 -> harding:0.0
$ echo $?
0
```

`send` triages, sends, then reads the pane back looking for the id. Exit `0` means *delivered and
confirmed*. Exit `2` means sent-but-unconfirmed — record nothing and re-dispatch, because a tracker
full of work nobody was told about is worse than a dropped message.

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

**Orienting on a graph you've never seen.**

```text
> use graph-report

# Graph Report — graph.example.com

## Overview
599 entities · 3,412 facts · 34 predicates

## God nodes (schema + episode nodes excluded)
1. db.example.com      DatabaseService   in-degree 41
2. node01              BareMetalHost     in-degree 33
3. traefik             ReverseProxyRoute in-degree 19

## Suggested questions
- What runs_on node01?
- What depends_on db.example.com, transitively?
- Which services have NO runs_on edge at all?
```

## Why Skein?

|  | **Hand-rolled prompts** | **MCP servers** | **LangChain-style frameworks** | **Agent plugin systems** | **[Gas Town](https://github.com/gastownhall/gastown)** | **skein** |
|--|:---:|:---:|:---:|:---:|:---:|:---:|
| Agent-agnostic (no vendor format)     | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| No server or daemon to operate        | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Install = copy a directory            | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Version-controlled and diffable       | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| No language/runtime dependency        | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Typed tool contract & auto-discovery  | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Multi-agent orchestration & lifecycle | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |

The last two rows are the honest ones. **skein is not an orchestrator and does not want to be.**

[Gas Town](https://github.com/gastownhall/gastown) is a full multi-agent workspace manager — session
lifecycle, work routing, the lot — and it does far more than a directory of markdown files can. We
run a fleet on it. But operating a fleet taught us that handing work to another agent is a
*surprisingly small* operation underneath: create an item, check the target pane is ready, send via
`tmux`, verify it landed. `dispatch-work` distills exactly that one capability into something you
can carry into any agent, on any machine, without adopting a workspace manager to get it. Reach for
Gas Town when you want the whole workshop; reach for skein when you want one tool in your pocket.

Requirements in full: `curl`, `tmux` (dispatch only), and Python 3 standard library (dispatch only).
No packages, no lockfile, no build step.

## The Skills

| skill | what it does |
|---|---|
| 📮 **dispatch-work** | Hand a work item to another agent — create it, check the pane is ready, send via `tmux`, verify it landed. Refuses to interrupt a busy agent. |
| 🚀 **homelab-deploy** | Deploy services to hosts — binaries, configs, IaC, rollback. IaC-first, verify-after. |
| 🩺 **homelab-patrol** | Health checks and diagnostics across a fleet. "What's broken?" — answered from live data, never memory. |
| 🔎 **quipu** | Query a knowledge graph before you act — what do we already know about this thing, and what is the graph *not* to be trusted about? |
| 🧬 **graph-extract** | Extract entities and relationships from docs, code, and issues into the graph as a structured episode. |
| 🗺️ **graph-report** | Orientation report over a graph — size, central entities, recent activity, suggested questions. |
| 📋 **planning-with-files** | File-based planning for multi-step work. Survives a context reset. |

The three graph skills assume a [Quipu](https://github.com/scbrown/quipu)-compatible RDF/SPARQL
endpoint. `planning-with-files` uses optional Claude Code hooks; the file discipline itself is
agent-agnostic. The rest assume nothing.

## Features

🧵 **Portable by construction** — A skill is a `SKILL.md` and, at most, a stdlib Python script. There
is no plugin API to target, so there is nothing to port when you change agents.

🔌 **Zero install** — `cp -r skills/<skill> ~/.claude/skills/`. That's the whole procedure. No
package manager, no lockfile, no build, no daemon to keep alive.

🌐 **Shell + HTTP only** — Every integration is `curl` against a documented endpoint, or `tmux`
against a pane. If you can reach it from a terminal, the skill works.

⚙️ **Config, not constants** — Every target is an environment variable (`GRAPH_URL`, `GRAPH_NS`,
`DB_HOST`, `DISPATCH_*`). A skill that hardcodes a hostname is ours, not yours — and we treat one
that slips through as a bug.

🧪 **Checks that can fail** — Every skill that verifies something documents how to *make it fail*.
`dispatch-work` ships `test_dispatch.py` exercising all four triage outcomes. A health check that
has never returned red is not a check.

🚦 **Honest exit codes** — `dispatch.py` branches without parsing prose: `0` delivered and confirmed,
`2` sent but unconfirmed, `3` refused because the pane wasn't ready. Ambiguity is a bug, not a
nuance.

🧠 **Encodes the caveat, not just the API** — The `quipu` skill spends as much space on what the
graph will *lie* to you about (unresolved duplicate entities, SHACL validating nothing, a swallowed
HTTP 400 that reads as "0 results, all clean") as on how to query it.

📋 **Survives a context reset** — `planning-with-files` keeps the plan, findings, and progress on
disk, so a cleared session picks up where the last one stopped.

## Configure

Skills read their targets from the environment. Nothing is hardcoded — see `.env.example`:

```bash
export GRAPH_URL=http://graph.example.com         # quipu / graph-extract / graph-report
export GRAPH_GROUP=my-ontology                    # graph partition to write into
export GRAPH_NS=http://example.org/ontology/      # IRI base for your own entities & classes
export SEARCH_URL=http://search.example.com       # optional: semantic code search
export DB_HOST=db.example.com                     # optional: data plane
export BEADS_DB=your_issues_db                    # optional: issue tracker db
```

`dispatch-work` has its own knobs (busy-marker patterns, context thresholds, tracker backend) —
all environment variables, documented in its `SKILL.md`.

## Install

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

## Status

Early. Extracted from a working homelab, generalised, and published with the intent of being useful
to someone who isn't us. If a skill leaks an assumption about our environment, that's a bug — open
an issue.

## License

[MIT](LICENSE)
