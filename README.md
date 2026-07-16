# skein

**Agentic skills for the homelab.** A skein is a bundle of threads — this is the bundle you draw from.

Portable skills for LLM coding agents (Claude Code, Codex, Cursor, Gemini CLI, and anything else that
reads a `SKILL.md`). They need **shell + HTTP and nothing else** — no framework, no runtime, no
service to operate. Copy a directory in and it works.

## Why this exists

Most agent tooling assumes you're writing software. Almost none of it assumes you're **running
infrastructure** — deploying to containers you own, patrolling hosts that drift, and remembering what
broke six weeks ago. These are the skills a homelab operator actually reaches for.

They came out of a live 14-agent homelab, so they encode things you only learn by being wrong:
patrol before you trust a dashboard, query the graph before you name an entity, and never let a check
report success it hasn't earned.

## The skills

| skill | what it does |
|---|---|
| **homelab-deploy** | Deploy services to containers — binaries, configs, rollback. |
| **homelab-patrol** | Health checks and diagnostics across a fleet. "What's broken?" |
| **quipu** | Query a knowledge graph before you act — what do we already know about this thing? |
| **graph-extract** | Extract entities and relationships from docs/code/tickets into the graph. |
| **graph-report** | Orientation report over a graph — size, central entities, recent activity. |
| **planning-with-files** | File-based planning for multi-step work. Survives a context reset. |

The three graph skills assume a [Quipu](https://github.com/YOUR_ORG/quipu)-compatible RDF/SPARQL
endpoint. The rest assume nothing.

## Configure

Skills read their targets from the environment. Nothing is hardcoded:

```bash
export GRAPH_URL=http://your-graph.example    # quipu / graph-extract / graph-report
export GRAPH_GROUP=my-ontology                # graph partition to write into
export SEARCH_URL=http://your-search.example  # optional: semantic code search
export DB_HOST=your-db.example                # optional: data plane
export BEADS_DB=your_issues_db                # optional: issue tracker db
```

## Install

```bash
git clone <this repo> && cp -r skein/skills/<skill> ~/.claude/skills/
```

Or point your agent's skill path at `skills/`.

## Status

Early. Extracted from a working homelab, generalised, and published with the intent of being useful
to someone who isn't us. If a skill leaks an assumption about our environment, that's a bug — open an
issue.

## Conventions

- **Python, not bash**, for anything that makes a decision or parses JSON.
- **A check must be able to fail.** If a health check has never returned red, it isn't a check.
  Every skill that verifies something says how to prove it can fail.
- **Config, not constants.** A skill that hardcodes a hostname is ours, not yours.

## Licence

See `LICENSE`.
