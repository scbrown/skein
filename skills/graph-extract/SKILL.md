---
name: graph-extract
description: >-
  Extract entities and relationships from source material (text, docs, code, issues, PDFs) and
  ingest them into a Quipu knowledge graph as a structured episode. Portable: works from any LLM
  agent — it only needs shell and HTTP, no framework. Triggers on "extract to graph",
  "ingest into quipu", "build knowledge graph from", "graph-extract", "add this to the ontology",
  or when asked to capture knowledge from a document/issue/repo into the graph. Auto-detects two
  modes: a pre-specified ingest request (entities/relationships already listed) or raw source
  material to extract from scratch.
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - WebFetch
---

# graph-extract — source material → Quipu knowledge graph

This skill is the portable, LLM-agnostic way to get knowledge into a graph. **You** (the agent) do
the extraction — the cheap, mechanical part — and POST a structured episode to Quipu's HTTP API. No
pipeline, no worker pool, no job runner. It runs anywhere there's a shell and network access to the
graph.

**Stack tools this reaches for**

| Present | This skill uses it for | Absent — what happens |
|---|---|---|
| **[Quipu](https://github.com/scbrown/quipu)** at `${GRAPH_URL}` | **required.** `POST /episode` is the entire write path | nothing is ingested. Save the assembled nodes/edges and retry — never report a write you did not observe |
| **[quipu](../quipu/SKILL.md)** skill | checking whether an entity already exists, so facts attach instead of forking a duplicate | you will create a second node for a thing that already had one — see that skill's Limit (a) |
| **[bobbin](https://github.com/scbrown/bobbin)** | reading the source material when it is a codebase rather than a document | `Read`/`Glob`/`Grep`, which is fine for a file and poor for a repo |

**This skill requires a running Quipu endpoint.** It writes; there is no offline
mode. If the graph is unreachable, the correct outcome is an explicit failure and
a saved payload, not a shrug — see Failure Modes.

**Skill resources:** the verified episode schema and the entity/relationship taxonomy are in
`{baseDir}/references/episode-schema.md` and `{baseDir}/references/taxonomy.md`. Read them before
your first POST.

**Graph endpoint:** `${GRAPH_URL}/episode` (group `${GRAPH_GROUP}`). Set it to a **hostname**,
never a raw private IP — IPs move, and a hardcoded one turns a portable skill into yours only.

## Essential Principles

1. **One fact per edge, no speculation.** Every edge is `{source, target, relation}` — all three
   required. Only assert what the source material actually states. If you're guessing, tag it (see
   confidence, principle 5) rather than inventing a clean-looking fact.

2. **Name entities concretely and canonically.** `node01`, not "the host". `search-api`, not "the
   search service". Reuse names already in the graph so facts attach to existing entities instead
   of forking duplicates — query first (`/query`) when unsure, or use Quipu's resolve step.

3. **The store is the source of truth — verify the write took.** A successful POST returns HTTP
   200 with `count > 0` (triples written) and a `tx_id`. Treat `count: 0` or any non-200 as a
   FAILURE (see Failure Modes). Do not trust the optional SPARQL regex self-check — `regex(str(?l))`
   FILTERs are unreliable on this Quipu; key success on `count` + `tx_id`.

4. **Minimum viable episode: ≥2 nodes and ≥1 edge.** If you can't extract that much that's real,
   skip — don't pad the graph with trivia.

5. **Tag uncertainty.** When the store supports a `confidence` qualifier on edges, mark each one
   `EXTRACTED` (explicitly stated, e.g. a config line), `INFERRED` (a reasonable deduction), or
   `AMBIGUOUS` (uncertain — flagged for human review). Auto-extracted facts SHOULD carry a tag.

## Workflow

### 1. Detect mode and gather source material
- **Pre-spec mode** — the request already lists `ENTITIES:` / `RELATIONSHIPS:` and names source
  issue(s) ("extract knowledge from <SRC>"). Read each SRC fully; the listed entities/relationships
  are your backbone — your job is to structure them and write accurate descriptions.
- **Raw mode** — you're handed a document, file, repo path, or issue. THAT is the source. Read it in
  full (`Read`/`Glob`/`Grep` for files; `WebFetch` for URLs; your tracker's show command for issues).
  Follow references inside it (linked issues, commit hashes, file paths) one hop.

### 2. Extract nodes and edges
Map the material onto the taxonomy in `{baseDir}/references/taxonomy.md`:
- **Nodes:** `{name, type, description}` — `type` is an entity label from the taxonomy;
  `description` is a one-line fact.
- **Edges:** `{source, target, relation}` — `relation` from the taxonomy's relationship vocabulary;
  `source`/`target` are node names.
- Prefer results and learnings (what was done, who did it, what was discovered) over restating the
  task. For dated events use `deployed_on` / temporal relations.

### 3. POST the episode
See `{baseDir}/references/episode-schema.md` for the exact JSON shape. Skeleton:

```bash
curl -s -m 20 -w '\nHTTP %{http_code}\n' ${GRAPH_URL}/episode -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "<episode-name>",
    "episode_body": "<short factual paragraph of the source>",
    "source": "graph-extract",
    "group_id": "${GRAPH_GROUP}",
    "nodes": [ {"name":"...","type":"...","description":"..."} ],
    "edges": [ {"source":"...","target":"...","relation":"..."} ]
  }'
```

Episode `name`: `ingest-<src-id>` for a pre-spec'd source, or `<topic>-<date>` for raw material.

### 4. Confirm and (optionally) annotate the source
- On HTTP 200 + `count > 0` + `tx_id`: done. If you read from a tracker issue, label the source
  `ontology-ingested` so it isn't re-processed.
- The episode is now queryable: `POST /query` (SPARQL) or `/search_nodes`.

## Failure Modes

| Situation | Action |
|-----------|--------|
| `${GRAPH_URL}` unreachable / non-200 / `count: 0` | Do NOT mark the source ingested. Save the assembled `nodes`/`edges` (note: `KNOWLEDGE-PENDING-INGESTION`) so a retry re-runs cleanly. |
| < 2 nodes or < 1 edge extractable | Skip — nothing knowledge-worthy. Say so explicitly. |
| Referenced source missing | Ingest what's available; don't fail the whole run. |
| SHACL validation rejects the write (400) | Read the violation (focus node / path / message), fix the node `type` or a required property, retry. |

## Portability notes

This skill depends only on `curl` + the Quipu HTTP contract. To point it at a different graph,
change the endpoint. To run it from a non-Claude agent, the only Claude-specific piece is the skill
wrapper — the workflow (read source → extract nodes/edges → POST) is plain instructions any capable
LLM can follow. The capability travels with the prompt, not with a platform.
