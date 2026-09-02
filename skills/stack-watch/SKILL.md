---
name: stack-watch
description: >-
  Run a cross-repo stack pass — look BETWEEN the repositories of one stack rather than
  inside any of them, and bead the places they disagree. Three lenses: consistency of
  tooling surfaces, leverage propagation (a capability shipped in one repo that its
  consumers have not adopted), and gaps between repos (the same thing built twice and
  drifted). The rules are DATA in the knowledge graph, so adding, retiring or softening
  one is a graph write and never a redeploy. Read-only against every repository.
  Triggers on "stack pass", "cross-repo consistency", "which repos disagree", "who has
  not adopted X", "duplicated across repos", "drifted conventions". Use repo-watch for a
  single repository; this is its between-repos sibling.
allowed-tools:
  - Bash
  - Read
  - Grep
---

# stack-watch — where do these repos disagree with each other?

A repo-watch pass looks INWARD at one repository. This one looks BETWEEN them.

It changes nothing. Same rule as its sibling: no commits, pushes, merges, deploys, or
issue/PR mutation. The only writes are beads.

## Norms are DATA, and that is the whole design

Every rule this pass applies is an entity in the graph carrying its own check, its own
tier, and the decision that created it — the same shape the internal-identifier patterns
use. Adding a norm, retiring one, correcting one, or changing how loudly it speaks is a
**graph write**. Nothing here needs a release for any of that.

That is not tidiness. It was load-bearing on the very first run: a norm whose target was
written as a directory (`.github/workflows`) produced **two false positives**, because
the file listing it is matched against contains files, not directories. The fix was one
`/set` changing the target to `.github/workflows/*` — the pass's behaviour changed with
no redeploy, no restart, and no code edit. A norm that could only be corrected by
shipping a release would have stayed wrong until someone had time to ship one.

    entity     a:Policy
    a:normCheck        path_present | path_absent
    a:normTarget       a path, a basename, or a trailing-glob prefix
    a:enforcementTier  warn | block          <- the graph's OWN vocabulary
    a:sourceDecision   the bead that decided it
    a:exemptRepoRegex  optional; repos matching are skipped

**The tier values are `warn` and `block` because those are what the store already uses.**
The plan calls these tiers "advise" and "enforce"; they are the same two things, and
minting a second vocabulary for them would fork the one concept the tiering exists to
make queryable.

**An absent tier ADVISES. A misspelled tier ADVISES.** Only the graph's explicit `block`
enforces. `tier != warn` would have been the natural expression and it is the wrong one:
a typo in a data field would start blocking people's work.

## Step 1 — read the file list AT EACH REPO'S ANCHOR

Not from working trees. A stack pass compares repos *against each other*, so one dirty
checkout would report its owner's uncommitted experiment as a stack-wide inconsistency,
attributed to everyone else.

> ⚠️ **An unresolvable anchor EXCLUDES a repo; it never counts as clean.** Measured on
> the first run: a recorded anchor was off by one character (`03e0c83f` for a commit
> whose sha is `03e0c831`) and did not resolve. The pass dropped that repo and said so.
> Had it treated the missing listing as an empty one, every norm would have "failed" for
> that repo at once — a transcription slip rendered as a repo-wide collapse.

## Step 2 — the three lenses

### Consistency
Every (repo, norm) pair that deviates. This is where "style and taste" live, and they
live as data: the pass has no opinion of its own.

### Leverage propagation
Repo A shipped capability K; which consumers have not adopted it? Deliberately a **text
reference** check and deliberately weak — a consumer that names the capability anywhere
counts as aware of it, and only total silence is reported. This lens finds repos that
have never *heard* of a capability. Judging how well they use it would manufacture a
finding against every repo that adopted it differently than expected.

### Gaps between repos
Files present in several repos under one name whose contents DISAGREE. **Identical
copies are not reported** — a deliberately shared file is a convention, not a defect,
and listing every duplicate would bury the drift in the list meant to reveal it.

## Step 3 — measure the false-positive rate. Do not assert it.

```python
led = stack_watch.FPLedger()
led.record("some-repo/norm_ci_workflow_present", real=False)   # adjudicated, one at a time
ok, why = stack_watch.gate_promotion(led)
```

`rate` is **None** when nothing has been adjudicated, and `None` is not zero. An
unmeasured rate reported as perfect is exactly how a norm gets promoted to blocking on
no evidence.

`gate_promotion` refuses on all three: nothing measured, a sample below the floor, or any
false positive at all. **A measured zero over two findings is not a soak** — the floor is
what stops a quiet week being read as proof.

## Step 4 — bead, anchor, report

One bead per real deviation, deduped against the full corpus like any other pass, and one
stack report naming every lens including the ones that found nothing. The pass is a signed
shuttle advance on the same workflow record as a repo pass — one audit discipline for both.

## Failure modes

| what you will see | what it means |
|---|---|
| a norm fires on every repo at once | its `normTarget` is probably a directory; the listing has files |
| a repo silently absent from results | its anchor did not resolve — that is a finding, not a clean repo |
| a norm blocking that should advise | check the tier's spelling in the graph, not the code |
| FP rate reported as 0% | check `adjudicated` — an unmeasured rate prints as UNMEASURED, and anything else is a real count |
