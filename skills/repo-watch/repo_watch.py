"""repo-watch — the deterministic half of a watch pass.

The SKILL.md carries the procedure an agent follows. This module carries the parts
that must be the SAME every pass, because they are the parts a careful agent gets
wrong differently each time: how a repo's owner is resolved from the graph, what
counts as a duplicate of an existing bead, and what the flood cap does when a pass
finds more than it is allowed to mint.

Design notes that are load-bearing, not decoration:

* **No network, no I/O.** Every function here is pure: text in, data out. The agent
  runs the HTTP and git; this module only builds queries and judges results. That is
  what makes the whole thing testable offline, which is the skein convention.

* **No internal identifiers.** Hosts, namespaces, repo names and owners arrive as
  arguments resolved at run time. Nothing internal is baked in — this file ships to a
  public mirror.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Ordered, and the order is the point. Plans establish intent; beads say what is
#: already claimed; docs state what was promised; code says what is true. Reading
#: them in this order means every later lens can cite an earlier one, and a gap is
#: always phrased as "X promises, Y delivers" rather than a bare complaint.
LENSES = ("plans", "beads", "docs", "code")

#: A pass may not mint more than this without an explicit override. A watcher that
#: floods the board is worse than one that misses something: the misses stay
#: findable, the flood buries everything else.
DEFAULT_MINT_CAP = 7


class ResolutionError(Exception):
    """The graph could not name an owner for this repo.

    Deliberately fatal rather than defaulted. A watch pass whose owner is a guess
    mints beads at the wrong person, and an unowned repo is a real, recorded state
    here — not an accident to paper over.
    """


@dataclass
class Resolution:
    """What the graph knows about one repo, resolved at run time."""

    repo: str
    owner: str | None = None
    ownership_state: str | None = None
    remotes: list[str] = field(default_factory=list)

    @property
    def ruled(self) -> bool:
        return self.owner is not None and self.ownership_state == "RULED"


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_query(name: str, ns: str) -> str:
    """SPARQL resolving one repo name to owner, ownership state and remotes.

    Three properties of this query are deliberate and each one was paid for:

    1. **Path-free.** The natural expression is an alias traversal
       ``?e (owl:sameAs|^owl:sameAs)* ?canon``. The store's aliases are DENORMALISED
       — every alias is carried on the canonical entity as both ``rdfs:label`` and
       ``skos:altLabel`` — so a plain UNION over those two is already total, and it
       stays total without depending on how the endpoint evaluates zero-or-more
       paths. (That evaluator has been wrong before, resolving 2 of 7 names while the
       data was perfect; it is fixed now, and this query never depended on it.)

    2. **DISTINCT.** Denormalisation means a name frequently matches BOTH the label
       and an altLabel of the same entity, so the un-deduplicated form returns the
       same owner two or three times. Nothing is wrong when that happens, but a
       caller counting rows would read it as ambiguity.

    3. **OPTIONAL on state and remotes.** A repo with an owner but no recorded
       ownership state must still resolve. Making these required turns a partially
       described repo into an unresolvable one, which reads as "the resolver is
       broken" instead of "the graph is incomplete here".

    One line on purpose: the query endpoint takes JSON, and a JSON string cannot
    carry literal newlines.
    """
    if not name or not name.strip():
        raise ValueError("repo name is required")
    if '"' in name or "\\" in name:
        # The name is interpolated into a SPARQL literal. Anything that could close
        # that literal is refused rather than escaped — a watch pass never has a
        # legitimate reason to look up a name containing a quote.
        raise ValueError(f"refusing unsafe repo name: {name!r}")
    return (
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
        f"PREFIX a: <{ns}> "
        "SELECT DISTINCT ?owner ?state ?remote WHERE { "
        f'{{ ?e rdfs:label "{name}" }} UNION {{ ?e skos:altLabel "{name}" }} '
        "OPTIONAL { ?e a:owned_by ?owner } "
        "OPTIONAL { ?e a:ownershipState ?state } "
        "OPTIONAL { ?e a:hasRemoteHost ?remote } "
        "} LIMIT 50"
    )


def rows_of(payload: dict) -> list[dict]:
    """Rows out of either response shape the query endpoint can return.

    The default compact shape is ``{"rows":[{var: value}]}``; with
    ``Accept: application/sparql-results+json`` it is W3C
    ``{"results":{"bindings":[{var:{"value":...}}]}}``. Accepting both means a caller
    that adds an Accept header for some other reason does not silently start reading
    zero rows — which is the failure mode this whole skill exists to catch, one level
    down.
    """
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("rows"), list):
        return [r for r in payload["rows"] if isinstance(r, dict)]
    bindings = payload.get("results", {}).get("bindings")
    if isinstance(bindings, list):
        return [
            {k: v.get("value") for k, v in b.items() if isinstance(v, dict)}
            for b in bindings
            if isinstance(b, dict)
        ]
    return []


def local_name(iri: str | None) -> str | None:
    """``.../ontology/somebody`` -> ``somebody``. Left alone if it is not an IRI."""
    if not iri:
        return None
    return re.split(r"[/#]", iri.rstrip("/#"))[-1] or None


def resolution_of(name: str, payload: dict) -> Resolution:
    """Fold a query response into one Resolution.

    Raises ResolutionError when no owner comes back. The message names the two
    causes that actually occur and are not distinguishable from the empty result —
    the repo is genuinely unowned in the graph, or its owner is recorded only as
    prose in a comment, which a SPARQL resolver cannot see. Both are graph writes by
    the ownership-map owner, not something a watch pass should invent.
    """
    owners, states, remotes = [], [], []
    for row in rows_of(payload):
        if (o := local_name(row.get("owner"))) and o not in owners:
            owners.append(o)
        if (s := row.get("state")) and s not in states:
            states.append(s)
        if (r := row.get("remote")) and r not in remotes:
            remotes.append(r)

    if not owners:
        raise ResolutionError(
            f"no owner in the graph for {name!r}. Either the repo is genuinely "
            f"unowned, or its owner exists only as prose in a comment — a resolver "
            f"cannot see prose. Both are ownership-map writes; do not guess an owner."
        )
    if len(owners) > 1:
        raise ResolutionError(
            f"{name!r} resolves to {len(owners)} owners ({', '.join(sorted(owners))}). "
            f"That is an alias collision or a genuine dispute; either way a watch pass "
            f"must not pick one."
        )
    return Resolution(
        repo=name,
        owner=owners[0],
        ownership_state=states[0] if states else None,
        remotes=sorted(remotes),
    )


# --------------------------------------------------------------------------- #
# Dedupe before mint
# --------------------------------------------------------------------------- #

#: Words carried by so many bead titles that sharing them means nothing.
_STOP = frozenset(
    """a an the and or but if is are was were be been being to of in on at for with
    from by as it its this that these those not no do does did can could should
    would may might must will shall have has had we you they i""".split()
)

_WORD = re.compile(r"[a-z0-9]+")


def tokens(title: str) -> frozenset[str]:
    """Comparable words of a title: lowercased, stop-words and bead ids dropped.

    Bead ids are stripped deliberately. A gap bead's title frequently cites the bead
    it came from, and two candidates citing the SAME source are not thereby the same
    gap — leaving ids in makes unrelated findings look alike, which suppresses real
    work. That is the expensive direction of this error.
    """
    lowered = title.lower()
    lowered = re.sub(r"\b[a-z]{2,8}-[a-z0-9]{3,6}\b", " ", lowered)
    return frozenset(w for w in _WORD.findall(lowered) if w not in _STOP and len(w) > 2)


def similarity(a: str, b: str) -> float:
    """Jaccard overlap of two titles' comparable words, 0.0 - 1.0."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_duplicate(
    candidate: str, corpus: list[dict], threshold: float = 0.6
) -> dict | None:
    """The existing bead a candidate gap would duplicate, or None.

    ``corpus`` is the FULL bead corpus — every bead, not the ready pool and not a
    title search. Two reasons, both measured on this fleet: the ready listing
    truncates by default, so an absence read from it is frequently an artefact of the
    limit; and the store's own search matches titles only, so it reports a phrase
    living in a description or comment as simply not present.

    Closed beads count as duplicates. A gap that was found and fixed last week should
    not be re-minted this week — if it has regressed, that is a different bead with a
    different argument, and it deserves to be written as one.
    """
    best, best_score = None, threshold
    for bead in corpus:
        title = bead.get("title") or ""
        if not title:
            continue
        score = similarity(candidate, title)
        if score >= best_score:
            best, best_score = bead, score
    return best


def partition_mints(
    candidates: list[str], corpus: list[dict], cap: int = DEFAULT_MINT_CAP
) -> tuple[list[str], list[tuple[str, dict]], list[str]]:
    """Split candidate gaps into (mint, duplicate, deferred-by-cap).

    Dedupe runs BEFORE the cap. Doing it the other way round lets duplicates consume
    the budget and pushes real findings into the deferred pile — the pass would then
    report "hit the cap" while minting nothing new, which is the worst of both.

    Nothing is discarded. Everything over the cap comes back as its own list so the
    watch report can name what was held, rather than quietly dropping it.
    """
    if cap < 0:
        raise ValueError("cap must not be negative")
    mint: list[str] = []
    dupes: list[tuple[str, dict]] = []
    for c in candidates:
        if (hit := find_duplicate(c, corpus)) is not None:
            dupes.append((c, hit))
        else:
            mint.append(c)
    return mint[:cap], dupes, mint[cap:]


# --------------------------------------------------------------------------- #
# The watch anchor
# --------------------------------------------------------------------------- #

@dataclass
class Anchor:
    """Where the last pass stopped. ``sha is None`` means no pass has ever run."""

    repo: str
    sha: str | None = None
    run: str | None = None

    @property
    def bootstrap(self) -> bool:
        return self.sha is None


def code_range(anchor: Anchor, head: str) -> str | None:
    """The git range a code/docs lens should read, or None when nothing moved.

    On a bootstrap pass this returns None rather than a range covering all history.
    A first pass has no delta to report; claiming one would restate the entire repo
    as new findings. The honest first pass records the anchor and reads the current
    state, which is what the plans and beads lenses do anyway.
    """
    if anchor.bootstrap or anchor.sha == head:
        return None
    return f"{anchor.sha}..{head}"


def run_name(repo: str, head: str, stamp: str) -> str:
    """Deterministic shuttle run id: ``watch-<repo>-<sha8>-<stamp>``.

    Deterministic so that re-deriving it later finds the same run, and carrying the
    sha so two passes over an unchanged repo cannot collide into one run id.
    """
    safe = re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")
    if not safe:
        raise ValueError(f"repo name has no usable characters: {repo!r}")
    return f"watch-{safe}-{head[:8]}-{stamp}"
