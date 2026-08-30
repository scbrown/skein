---
name: repo-watch
description: >-
  Run a watch pass over one repository — read its plans, its open beads, its docs and its
  code delta through four ordered lenses, and mint a bead for every gap between what the
  repo promises and what it ships. Read-only against the repository: a watch pass never
  edits, pushes, merges, deploys, or touches an issue or pull request. Owner, remotes and
  norms are resolved from the knowledge graph at run time, never hardcoded. Triggers on
  "watch <repo>", "repo watch", "dream pass", "what has drifted in <repo>", "review this
  repo for gaps", "docs vs code drift", or a scheduled watcher role. Use graph-extract to
  write findings into the graph and quipu to read it.
allowed-tools:
  - Bash
  - Read
  - Grep
---

# repo-watch — what does this repo promise that it does not ship?

A watch pass reads one repository through four lenses, in order, and produces **one watch
report plus a bead for every gap it can evidence**. It changes nothing.

The unit of output is a gap: *X promises, Y delivers.* Not an opinion, not a wish, not a
refactor you would enjoy. If you cannot name both halves and cite where each lives, you
have not found a gap and you should not mint one.

## What this skill will not do

**It is read-only against the repository and against the forge.** No commits, no pushes,
no merges, no deploys, no branch or tag creation, no issue or pull-request mutation, no
comment on a pull request, no production action. The only writes a pass makes are bead
tracking and reporting, and an append to its own run log.

This is not caution for its own sake. A watcher is trusted precisely because its findings
cost nothing to ignore. The moment a pass can change the thing it is judging, every one of
its reports has to be audited before it can be believed, and the whole mechanism inverts.

## Before you start

1. **Resolve the repo from the graph.** Owner, remotes and ownership state are DATA. Never
   read them from this file, from a directory name, or from memory.
2. **Take a worktree you own.** A shared checkout's index and HEAD belong to the checkout,
   not to your process, so a sibling session's staging reaches into yours.
3. **Fetch before you anchor.** An anchor taken against a stale remote-tracking ref records
   a delta that has already been superseded, and every finding downstream inherits it.
4. **Fetch EVERY remote and compare them.** A repo with two remotes can have one of them far
   behind, and the tracked one is not always the current one. Anchoring on a remote that is
   behind produces a pass that reads a stale tree and reports "no delta" with total
   confidence. Record which remote you anchored on, and whether the others agree.

> ⚠️ **MEASURE IN THE TREE YOU ANCHORED ON.** This is the mistake this skill's own first pass
> made, so it is written at the top rather than in a footnote: the anchor was taken from the
> tracked remote, the measurements were run in the working checkout, and the checkout was 73
> commits ahead. Two of the four numbers in the first gap bead were wrong — each individually
> plausible, none reproducible from the stated anchor.
>
> A finding is only as good as the tree it was measured in, and a report that names one sha
> while quoting another tree's numbers is *worse* than an unmeasured one: it is falsifiable in
> principle and wrong in practice, so it survives review and fails later.
>
> Use `git show <anchor>:<path>` for single files, or a detached worktree at the anchor for
> anything needing a build or a test run — never the shared checkout, whose HEAD belongs to
> whoever last touched it.

## Step 1 — resolve the repo

```bash
Q() { curl -s --max-time 30 "${GRAPH_URL}/query" -X POST \
        -H 'Content-Type: application/json' -H 'X-Quipu-Client: repo-watch' \
        -d "$(jq -cn --arg q "$1" '{query:$q}')"; }
```

`repo_watch.resolve_query(name, ns)` builds the query. Three things about it are
deliberate, and each cost something to learn:

- **It uses no property path.** The obvious resolver traverses aliases with
  `?e (owl:sameAs|^owl:sameAs)* ?canon`. Aliases in this store are *denormalised* — every
  alias is carried on the canonical entity as both `rdfs:label` and `skos:altLabel` — so a
  plain `UNION` over those two is already total, and it stays total regardless of how the
  endpoint evaluates zero-or-more paths. That evaluator has been wrong before, resolving 2
  of 7 names against perfect data. It is fixed now. This query never depended on it.
- **It is `DISTINCT`.** Denormalisation means one name usually matches both the label and
  an altLabel of the same entity, so the un-deduplicated form returns each owner two or
  three times. Nothing is wrong when that happens, but a caller counting rows reads it as
  ambiguity.
- **State and remotes are `OPTIONAL`.** A repo with an owner but no recorded ownership
  state must still resolve; requiring them turns a partly-described repo into an
  unresolvable one, which reads as a broken resolver rather than an incomplete graph.

**If no owner comes back, STOP and say so.** Do not guess, and do not fall back to the
roster in your head. There are two causes and they are indistinguishable from the empty
result: the repo is genuinely unowned, or its owner is recorded only as prose in a
`rdfs:comment`, which SPARQL cannot see. Both are writes for whoever holds the ownership
map. A pass that guesses an owner mints work at the wrong person and looks authoritative
doing it.

## Step 2 — the four lenses, in this order

The order is the contract. Plans establish intent; beads say what is already claimed; docs
state what was promised; code says what is true. Reading them in this order means every
later lens can cite an earlier one, and every gap comes out phrased as a comparison rather
than a complaint.

### Lens 1 — plans

Read the design docs and any design-labelled beads. You are looking for **status banners
that contradict the repo's own history**: a plan marked "not started" for something that
shipped, a "rejected" decision the code now implements, two plans that assume different
answers to the same question.

### Lens 2 — beads

Read the **full corpus** — every bead, not the ready pool and not a title search. Both
shortcuts lie here and both lie reassuringly:

- The ready listing **truncates by default**, so an absence read from it is frequently an
  artefact of the limit. Ask for the whole thing, and say what limit you ran under.
- The store's search matches **titles only**. A phrase living in a description or a comment
  comes back as "not found" — in the exact words of a true absence. Grep the exported
  corpus instead.

This lens has prior art: a citation-drift check that compares each bead's `updated_at`
against the newest commit citing it by id. A commit newer than the bead is positive
evidence the world moved while the bead was not listening. **Reuse it rather than
rebuilding it** — that instrument exists because someone fixed a condition, cited the bead
by id in the commit subject, and the bead went on asserting the unfixed state underneath a
cluster of work built on it.

### Lens 3 — docs

Compare README and book/reference claims against the shipped surface, over the delta since
the last anchor. The productive question is not "are the docs complete" — they never are,
and that finding helps nobody. It is **"where do the docs state something the code has
stopped doing?"** A capability that moved leaves its old description behind, stated with
full confidence, and that is worse than an omission because a reader acts on it.

### Lens 4 — code

Read the delta since the anchor: `repo_watch.code_range(anchor, head)`. On a bootstrap pass
this is `None` — a first pass has no delta, and manufacturing one restates the entire
repository as new findings. Record the anchor, report the current state from the other
three lenses, and say plainly that it was a bootstrap.

## Step 3 — dedupe against the corpus, THEN cap

```python
mint, dupes, held = repo_watch.partition_mints(candidates, corpus, cap=7)
```

**Dedupe runs before the cap, and the order is load-bearing.** Reversed, duplicates consume
the budget and push real findings into the held pile — the pass then reports that it hit the
cap while minting nothing new, which is the worst of both outcomes.

Closed beads count as duplicates. A gap found and fixed last week must not be re-minted this
week; if it has genuinely regressed, that is a different bead with a different argument and
it deserves to be written as one.

Nothing is discarded. Everything over the cap comes back as `held` so the report can name
what it is holding.

## Step 4 — anchor the pass

The anchor is a **signed shuttle advance**, so that "when did we last look, and who looked"
is a fact in the record rather than a claim in prose.

```bash
shuttle start repo-watch "$(python3 -c 'import repo_watch,sys; ...')" --agent "$OWNER"
shuttle advance "$RUN" --step observed --agent "$OWNER"
shuttle export
```

> ⚠️ **A shuttle `/knot` lands in a WINDOW graph, not the root graph.** An anchor read back
> in default scope returns ZERO rows — which looks exactly like the advance never landed,
> and the natural recovery is to re-run it. **Read the window scope explicitly**, and verify
> the anchor by reading back the signed step, never from the run's exit code.

## Step 5 — the report

One watch report bead per pass. It must carry, because a reader two weeks from now cannot
reconstruct any of it:

- **the anchor** — the sha observed after fetch, and the run id;
- **each lens, named, with what it found or that it found nothing.** A lens that found
  nothing is a result and belongs in the report. A lens silently omitted is
  indistinguishable from a lens that was never run;
- **the mint ledger** — minted, deduped (with the bead each candidate matched), held by cap;
- **the safety line** — that nothing in the repository or on the forge was mutated;
- **evidence for every stated cause**, inline: the command and its output, or the word
  INFERRED.

Then tell the repo's owner. A report nobody is pointed at is a report nobody reads.

## Failure modes this skill is built around

| what you will see | what it actually means |
|---|---|
| resolver returns no owner | genuinely unowned, **or** owner recorded only as prose — STOP either way |
| resolver returns the same owner 3× | denormalised aliases; use `DISTINCT`, it is not ambiguity |
| anchor read returns 0 rows | you read root scope; the advance is in the **window** graph |
| bead search finds nothing | search matches **titles only** — grep the corpus |
| ready pool "does not contain it" | the pool **truncated**; state the limit or do not claim the absence |
| a lens found nothing | a result — report it, do not omit it |
| one remote far behind the other | anchor on the wrong one and every lens reads a stale tree |
| numbers that do not reproduce | you measured in the checkout, not at the anchor |
