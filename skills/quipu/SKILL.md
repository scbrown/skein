---
name: quipu
description: >-
  Query a Quipu knowledge graph before you act — what your ops graph already knows about a
  service, container, issue, or agent, and what the graph is NOT to be trusted about.
  Portable: shell + HTTP to ${GRAPH_URL} only, runs from any LLM agent, no framework.
  Triggers on "query before you act", "what do we know about <thing>", "ask quipu", "check the
  ontology", "blast radius", "what depends on X", "what runs on X", or before starting any task
  that names an entity. To ADD knowledge use graph-extract; to map the whole graph use
  graph-report. This skill is the read path.
allowed-tools:
  - Bash
  - Read
---

# quipu — query before you act

Your homelab's operational memory is an RDF graph at `${GRAPH_URL}`. It knows which services
depend on what, which host runs which container, what broke before and why. **Before you start a
task, ask the graph about the entities the task names.** That is the whole skill.

**Stack tools this reaches for**

| Present | This skill uses it for | Absent — what happens |
|---|---|---|
| **[Quipu](https://github.com/scbrown/quipu)** at `${GRAPH_URL}` | **required.** Every query on this page is Quipu's HTTP API | the skill does nothing. There is no fallback and pretending otherwise would be the exact failure it warns about |
| **[bobbin](https://github.com/scbrown/bobbin)** | the graph names a service; bobbin finds the code that implements it | you know *what* depends on it, not *where* it lives |
| **[hank](https://github.com/scbrown/hank)** | blast radius inside one codebase, where the graph's edges stop | service-level dependencies only |

**This skill requires a running Quipu endpoint** — that is a real dependency, and
it is stated here rather than buried. Any RDF store speaking the same HTTP
contract (`/query`, `/search`, `/stats`, `/episode`) works; `${GRAPH_URL}` is the
only thing to change. But with no graph, there is nothing to degrade *to*: an
operational memory you don't have cannot be approximated by grep, and this skill
will not pretend it can.

**Two graphs, two scopes** — the graph knows that `search-api` depends on
`db-server`; [hank](https://github.com/scbrown/hank) knows that
`parse_token()` is called by forty places inside it. Neither can answer the
other's question. Blast radius usually needs both.

This is the **read** path. Its two siblings:

- **[graph-extract]** — *write*. Add knowledge (`POST /episode`). Do not hand-roll ingestion; use it.
- **[graph-report]** — *orient*. Map the whole graph (god nodes, communities, surprises).

## Essential Principles

1. **A PREFIX declaration is REQUIRED.** Bare `rdfs:label` or `a:depends_on` is a hard parse error
   (`SPARQL parse error: ... Prefix not found`) — the endpoint declares no prefixes for you. This is
   the single most common way a first query fails. Copy the prefix block below every time.

2. **Keep the SPARQL on ONE line, or encode it with `jq`.** A JSON string cannot contain literal
   newlines, so the natural pretty-printed `-d '{"query":"\n  PREFIX ..."}'` fails with
   `control character (\x00-\x1f) found while parsing a string` — a JSON error that says nothing
   about SPARQL, so it reads like the graph is broken when it's just the quoting. SPARQL ignores
   whitespace; one long line is fine. For long queries use the heredoc + `jq` form in step 2.

3. **The response shape is content-negotiated — pick the one that fits.** The `/query` endpoint
   honours the `Accept:` header:
   - **Default / no `Accept` / `application/json`** — Quipu's own compact shape:
     `{"count":N,"rows":[{"var":"value"}],"variables":[...],"truncated":bool}` — flat rows, values
     already unwrapped. `ASK` returns `{"result":true}`; `CONSTRUCT` returns
     `{"count":N,"triples":[{subject,predicate,object}]}`. Convenient, but **lossy**: a literal that
     looks like a URL is byte-identical to a real IRI, and datatypes/language tags are dropped — so
     don't infer "this is a node" from a value that starts with `http`.
   - **`Accept: application/sparql-results+json`** — standard **W3C SPARQL 1.1 Results JSON**:
     `{"head":{"vars":[...]},"results":{"bindings":[{"var":{"type":"uri"|"literal","value":...}}]}}`.
     Use this when you need to tell an IRI from a literal — the `type` field disambiguates what the
     default shape flattens away. `results.bindings[].value` **does** exist on this path.
   - **`Accept: text/turtle` / `application/n-triples`** (CONSTRUCT only) — RDF serialization.
   Note: even the standard JSON path still **does not** carry datatype/language tags faithfully —
   so for datatyped/tagged literals, treat values as strings, not typed RDF terms.

4. **One real thing is many nodes — never trust a clean-looking answer.** Entity resolution may
   never have run (see Limits). One database can be *seven* separate `DatabaseService` nodes. A
   blast-radius query then returns a **subset that looks exactly like a complete answer**. That is
   worse than an error, because an error tells you it failed. Always widen with a `regex` label
   scan first.

5. **Ask the graph to show its work.** Counts drift hourly — a live graph gains facts all day. Ship
   *queries*, not remembered numbers. If you need a number, re-run the query; do not quote one from
   a doc or a ticket (including this file). *(Measured: every predicate count in this skill's first
   draft moved within 12 hours — `depends_on` 30→33, `prov:wasGeneratedBy` 950→991.)*

## Workflow

### 1. Cheapest first — semantic search

You rarely know the exact IRI. Start here; it is one call and needs no SPARQL:

```bash
curl -s ${GRAPH_URL}/search -X POST -H 'Content-Type: application/json' \
  -d '{"query":"database server"}'
```

Returns scored hits with a `text` summary and the real `entity` IRI:
`{"count":10,"results":[{"entity":"${GRAPH_NS}db-server.service",
"score":0.647,"text":"db-server.service. SQL server on ${DB_HOST}:3306, the data plane. ...
Fragile; a downstream service previously died for nine weeks via systemd stop-propagation from
this unit.","valid_from":"..."}]}`

That `text` is often the entire answer. Take the `entity` IRI into step 2.

### 2. SPARQL — two forms that work

**Short query — one line** (copy-paste, no dependencies). Note the escaped `\"` inside the JSON:

```bash
curl -s ${GRAPH_URL}/query -X POST -H 'Content-Type: application/json' \
  -d '{"query":"PREFIX a: <'"$GRAPH_NS"'> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?s ?l WHERE { ?s rdfs:label ?l . FILTER(regex(?l, \"db\", \"i\")) } LIMIT 20"}'
```

**Long query — heredoc + `jq`** (readable, handles quotes/newlines correctly). Prefer this once a
query outgrows one line:

```bash
read -r -d '' Q <<SPARQL
PREFIX a:    <${GRAPH_NS}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?s ?l WHERE { ?s rdfs:label ?l . FILTER(regex(?l, "db", "i")) } LIMIT 20
SPARQL
curl -s ${GRAPH_URL}/query -X POST -H 'Content-Type: application/json' \
  -d "$(jq -n --arg q "$Q" '{query:$q}')"
```

`jq` does the JSON escaping, so you write plain `"db"` instead of `\"db\"`. The heredoc delimiter is
left **unquoted** only so `${GRAPH_NS}` expands; if your query contains a literal `$` or backtick,
quote it (`<<'SPARQL'`) and paste the base IRI in directly. Both forms verified live.

`a:` is your ontology base (`${GRAPH_NS}`) — **classes and instances share it** (`a:Container` the
class, `a:${DB_HOST}` the instance).

### 3. Find every node for your entity — do this before any traversal

```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?s ?l WHERE { ?s rdfs:label ?l . FILTER(regex(?l, "<thing>", "i")) } LIMIT 20
```

If this returns several nodes for one real-world thing (it usually does), **every** subsequent
query must account for all of them. Verified live on a production graph: a `regex "db"` label scan
returned `a:db`, `a:Db`, `a:${DB_HOST}`, `a:db-server`, `a:db-server.service`, `a:app-db`, and
`a:local-db-fork` — seven nodes, one database.

### 4. What is this thing / what do we know about it

```sparql
PREFIX a: <${GRAPH_NS}>
SELECT ?p ?o WHERE { a:db-server.service ?p ?o }
```

`rdfs:comment` carries the prose an earlier agent wrote. `prov:wasGeneratedBy` points at the
*episode* that asserted the fact — follow it to learn *when and why* something was recorded.

### 5. Traversal — property paths DO work

Verified live: `depends_on+` (transitive) returns strictly more than plain `depends_on`, and
alternation `depends_on|runs_on` returns exactly the sum of both. So blast-radius queries are
viable **today**:

```sparql
PREFIX a: <${GRAPH_NS}>
SELECT ?dependent WHERE { ?dependent a:depends_on+ a:${DB_HOST} }
```

Re-run the pair below yourself to confirm paths still work before relying on one:
```sparql
SELECT (COUNT(*) AS ?n) WHERE { ?s a:depends_on  ?o }   # plain
SELECT (COUNT(*) AS ?n) WHERE { ?s a:depends_on+ ?o }   # transitive — must be >= plain
```

**But read Limit (a) before you believe the result.** In the measured case, that query returned a
real dependent for `a:${DB_HOST}` — and `0` for `a:db`. Same real-world thing, different node,
opposite answer.

### 6. What predicates exist (the graph's actual vocabulary)

Do not guess relationship names — ask:

```sparql
SELECT ?p (COUNT(*) AS ?n) WHERE { ?s ?p ?o } GROUP BY ?p ORDER BY DESC(?n) LIMIT 20
```

A typical domain vocabulary, in rough frequency order (the `prov:`/`rdfs:`/`rdf:` ones above them
are structural): `groupId`, `prov:wasAssociatedWith`, `invocation`, `capability_kind`, `runs_on`,
`depends_on`, `contentHash`, `authored_by`, `owns`, `applies_to`. Full vocabulary and entity types:
`{baseDir}/../graph-extract/references/taxonomy.md`.

### 7. Graph size / liveness

```bash
curl -s ${GRAPH_URL}/stats     # {"entities":N,"facts":N,"predicates":N}
curl -s ${GRAPH_URL}/report    # nodes, edges, communities, hubs, suggested_questions
```

## Limits — say these out loud before you trust an answer

These are **live-verified**, not folklore. They are the difference between using the graph and being
misled by it. Re-verify each against your own deployment — the flags below are defaults, and a
default is exactly the kind of thing that quietly stays off.

**(a) Entity resolution may never have fired.** `resolution.enabled` defaults false, and a deployed
config that never sets it leaves one real thing as many nodes. Verified live: seven separate nodes
typed `DatabaseService` matched `regex "db"`. Consequence: `?x depends_on+ a:db` returned **0**
while `?x depends_on+ a:${DB_HOST}` returned a real dependent. A blast-radius answer is then a
*subset presented as a whole* — for triage, worse than no answer. **Mitigation:** always run the
step-3 label scan and union across every node you find.

**(b) SHACL may be validating NOTHING.** `validate_on_write` defaults false. Verified live on a real
deployment: `POST /shapes` → `{"count":0,"shapes":[]}`. With zero shapes loaded, nothing constrains
what gets written; a fact in the graph passed no schema check. `POST /validate` requires you to
supply `shapes` inline — there is no stored shape set to fall back on.

**(c) `owl:sameAs` and `quipu:distinctFrom` are often unused** — verified live at 0 uses. So there
is not even a manual alias layer papering over (a): you cannot look up "what else is this same
thing".

**(d) These limits share one pattern.** A capability is present, its flag defaults off, the deployed
config never sets it, and every surface signal reports healthy. Endpoint answers ≠ endpoint acts.
Ask any capability to show its work — `count > 0` — before believing it.

**(e) Asking "what is MISSING?" — the engine refuses the obvious idioms, and a careless client turns
the refusal into a clean answer.** The SPARQL engine does **not** support:

```
FILTER NOT EXISTS { ... }     FILTER(?x IN (...))     VALUES ?x { ... }     MINUS { ... }
```

Each returns **HTTP 400** with `{"error": "unsupported ..."}` and **no `"rows"` key**. The server is
honest — *your client is where the lie gets made*:

```python
rows = d.get("rows", [])        # ← a 400 refusal becomes []  →  "0 results, graph is clean"
```

**Check the status code** (it is 400 — that alone catches all four), or check for an `error` key
**before** reading `rows`. An errored query is not a *zero* result, it is *no* result.

Use the sanctioned negation idiom instead — verified exact against `/stats` (565 + 34 = 599
entities):

```sparql
SELECT ?s WHERE { ?s ?p ?o . OPTIONAL { ?s a:runs_on ?x } FILTER(!bound(?x)) }
```

> **A gap-detector that has never returned a row is indistinguishable from a broken one.** Run a
> positive control on a predicate you can *prove* most nodes lack, and confirm it returns rows,
> before you believe a zero. This rule was paid for: an agent reported "0 ghosts — the graph is
> clean" off a swallowed 400, and only a forced positive control caught it.

## When to use

- **Before starting any task** — search the entities it names (step 1). Two minutes here beats
  rediscovering that `db-server.service` propagates systemd stops to everything downstream.
- **Before touching a service** — blast radius (step 5), then widen per Limit (a).
- **When a task references history** ("this broke before") — the `rdfs:comment` + episode trail.

## Wiring it into your agent (optional, and where it breaks)

You shouldn't have to remember this skill exists. If your agent supports session-start hooks, inject
a short **live** orientation — current entity/fact counts, the search + SPARQL recipes, and the
trust limit — at the top of every session:

```bash
curl -s -m 3 ${GRAPH_URL}/stats || exit 0    # fail SILENT — never wedge a session on a graph outage
```

Four things learned the hard way, all agent-agnostic:

- **Fail silent, always.** Exit 0 with no output when the graph is unreachable. A hook that *can*
  block a session start will eventually block one.
- **Keep hook output under ~2KB.** Most runtimes truncate large session-start stdout to a preview
  and spill the rest to a file the model never reads — so a 20KB primer mostly does not reach the
  agent at all.
- **Register the hook where your tooling regenerates from, not only in the generated file.** If a
  config generator rebuilds `settings.json` from a base plus overrides, a hand-edit to the generated
  file is erased by the next sync. Put it in the override, then diff to confirm a sync reproduces it.
- **Respawned or handed-off sessions may load no hooks at all.** If your launcher drops its settings
  flag on respawn, a cycled session gets *no* orientation. That is why this file must stand on its
  own — assume the reader arrived with nothing.

## Adding knowledge

Use **[graph-extract]** (`POST /episode`, group `${GRAPH_GROUP}`). Do not hand-roll a POST — it
handles node/edge shape, provenance, and the taxonomy. Knowledge has to reach the graph, not just a
document: a doc nobody queries is a doc nobody reads.

[graph-extract]: ../graph-extract/SKILL.md
[graph-report]: ../graph-report/SKILL.md
