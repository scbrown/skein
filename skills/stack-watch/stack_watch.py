"""stack-watch — the deterministic half of a cross-repo stack pass.

A repo-watch pass looks INWARD at one repository. This one looks BETWEEN them: it asks
whether the repos that make up one stack agree with each other about tooling, whether a
capability shipped in one has reached the consumers that should use it, and whether the
same thing has been implemented twice and drifted apart.

**Norms are DATA, not code.** Every rule this module applies is an entity in the graph
carrying its own check, its own tier and the decision that created it. Adding or
retiring a norm is a graph write; nothing here needs a redeploy for the pass to start
or stop applying a rule, or to change how loudly it speaks. That is not a nicety — it
is what lets a rule be softened at 3am by whoever is awake, without a release.

**The tier vocabulary is the graph's, not a new one.** The store already uses
``enforcementTier`` with values ``warn`` and ``block``. The plan calls these tiers
"advise" and "enforce"; those are the same two things under different names, and
minting a second vocabulary for them would fork the one concept the tiering exists to
make queryable.

No network, no I/O: the caller runs git and HTTP, this judges the results.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field

#: Ordered. Consistency establishes what the stack agrees on; leverage asks who is
#: behind; gaps asks what was built twice. Each later lens reads better once the
#: earlier one has said what "normal" looks like across these repos.
LENSES = ("consistency", "leverage", "gaps")

#: The graph's own tier values. `warn` advises, `block` enforces. Anything else is
#: treated as `warn` — an unrecognised tier must not silently escalate to blocking.
TIER_ADVISE = "warn"
TIER_ENFORCE = "block"


class NormError(Exception):
    """A norm in the graph is not usable as written."""


@dataclass
class Norm:
    """One cross-repo rule, exactly as the graph states it."""

    name: str
    label: str = ""
    comment: str = ""
    #: what kind of check: "path_present" | "path_absent"
    check: str = "path_present"
    #: the path or glob the check is about
    target: str = ""
    #: the graph's enforcementTier
    tier: str = TIER_ADVISE
    #: the bead that decided this norm exists
    source: str = ""
    #: optional regex; repos whose name matches are exempt
    exempt: str = ""

    @property
    def enforcing(self) -> bool:
        """True only for the graph's explicit enforce value.

        Deliberately not `tier != TIER_ADVISE`. An unknown or misspelled tier would
        then read as enforcing, which is the one direction a rules engine must never
        fail in: a typo in a data field would start blocking work.
        """
        return self.tier == TIER_ENFORCE

    def applies_to(self, repo: str) -> bool:
        if not self.exempt:
            return True
        try:
            return re.search(self.exempt, repo) is None
        except re.error:
            # A broken exempt pattern must not silently widen the norm's reach.
            raise NormError(f"norm {self.name!r} has an invalid exemptRegex: {self.exempt!r}")


def norm_query(ns: str) -> str:
    """SPARQL for every stack norm the graph holds.

    Path-free and DISTINCT for the same reasons the repo resolver is; OPTIONAL on
    everything but the name, because a norm missing its comment is still a norm and
    should not vanish from the pass because its prose was never filled in.
    """
    return (
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        f"PREFIX a: <{ns}> "
        "SELECT DISTINCT ?n ?label ?comment ?check ?target ?tier ?source ?exempt WHERE { "
        "?n a a:Policy ; a:normCheck ?check ; a:normTarget ?target . "
        "OPTIONAL { ?n rdfs:label ?label } "
        "OPTIONAL { ?n rdfs:comment ?comment } "
        "OPTIONAL { ?n a:enforcementTier ?tier } "
        "OPTIONAL { ?n a:sourceDecision ?source } "
        "OPTIONAL { ?n a:exemptRepoRegex ?exempt } "
        "} LIMIT 200"
    )


def norms_of(rows: list[dict]) -> list[Norm]:
    """Fold query rows into Norms, newest-wins on duplicate names."""
    out: dict[str, Norm] = {}
    for r in rows:
        name = (r.get("n") or "").rsplit("/", 1)[-1]
        if not name:
            continue
        out[name] = Norm(
            name=name,
            label=r.get("label") or name,
            comment=r.get("comment") or "",
            check=r.get("check") or "path_present",
            target=r.get("target") or "",
            # An ABSENT tier advises. A norm whose tier nobody set must not block.
            tier=r.get("tier") or TIER_ADVISE,
            source=r.get("source") or "",
            exempt=r.get("exempt") or "",
        )
    return sorted(out.values(), key=lambda n: n.name)


# --------------------------------------------------------------------------- #
# Lens 1 — consistency
# --------------------------------------------------------------------------- #

def _matches(paths: list[str], target: str) -> bool:
    """Does any path satisfy `target`? Exact match, or a trailing-glob prefix."""
    if target.endswith("*"):
        stem = target[:-1]
        return any(p == stem.rstrip("/") or p.startswith(stem) for p in paths)
    return any(p == target or posixpath.basename(p) == target for p in paths)


@dataclass
class Deviation:
    """One repo failing one norm."""

    repo: str
    norm: Norm
    detail: str

    @property
    def enforcing(self) -> bool:
        return self.norm.enforcing

    def title(self) -> str:
        return f"{self.repo}: {self.norm.label or self.norm.name}"


def consistency(norms: list[Norm], repo_paths: dict[str, list[str]]) -> list[Deviation]:
    """Every (repo, norm) pair that deviates.

    `repo_paths` maps repo name -> its file list AT ITS ANCHOR. Reading the anchor
    rather than a working tree matters here more than anywhere: a stack pass compares
    repos against each other, so one dirty checkout would report its owner's
    uncommitted experiment as a stack-wide inconsistency.
    """
    out = []
    for repo, paths in sorted(repo_paths.items()):
        for norm in norms:
            if not norm.applies_to(repo):
                continue
            present = _matches(paths, norm.target)
            if norm.check == "path_present" and not present:
                out.append(Deviation(repo, norm, f"missing {norm.target}"))
            elif norm.check == "path_absent" and present:
                out.append(Deviation(repo, norm, f"present but should not be: {norm.target}"))
    return out


# --------------------------------------------------------------------------- #
# Lens 2 — leverage propagation
# --------------------------------------------------------------------------- #

def leverage_gaps(capability: str, producer: str,
                  consumers: dict[str, list[str]]) -> list[str]:
    """Consumers that do not yet reference a capability their producer shipped.

    Deliberately a TEXT REFERENCE check, and deliberately weak. A consumer that names
    the capability anywhere is treated as aware of it; only total silence counts. That
    asymmetry is on purpose — this lens exists to find repos that have never heard of a
    new capability, not to audit how well they use it. Judging quality here would
    manufacture findings against every repo that adopted it differently than expected.
    """
    if not capability:
        return []
    needle = capability.lower()
    return sorted(name for name, blobs in consumers.items()
                  if name != producer
                  and not any(needle in (b or "").lower() for b in blobs))


# --------------------------------------------------------------------------- #
# Lens 3 — gaps between repos
# --------------------------------------------------------------------------- #

def drifted_twins(files: dict[str, dict[str, str]]) -> list[tuple[str, list[str]]]:
    """Files that exist in several repos under one name and DISAGREE.

    `files` maps repo -> {basename: content-hash}. Returns (basename, repos) for every
    name present in 2+ repos with more than one distinct hash.

    Identical copies are NOT reported. A file deliberately shared across repos is a
    convention, not a defect; only divergence is evidence of anything, and reporting
    every duplicate would bury the drift in the very list meant to reveal it.
    """
    by_name: dict[str, dict[str, str]] = {}
    for repo, mapping in files.items():
        for name, digest in mapping.items():
            by_name.setdefault(name, {})[repo] = digest
    out = []
    for name, per_repo in sorted(by_name.items()):
        if len(per_repo) >= 2 and len(set(per_repo.values())) > 1:
            out.append((name, sorted(per_repo)))
    return out


# --------------------------------------------------------------------------- #
# False-positive accounting
# --------------------------------------------------------------------------- #

@dataclass
class FPLedger:
    """Measured false-positive rate. Measured, never asserted.

    The plan requires the rate to be MEASURED rather than claimed, so the pass records
    a verdict per deviation and computes from those. A ledger with nothing adjudicated
    reports `None`, not zero: an unmeasured rate is not a perfect one, and reporting it
    as zero is exactly how an advise tier gets promoted to blocking on no evidence.
    """

    confirmed: list[str] = field(default_factory=list)
    false_positive: list[str] = field(default_factory=list)

    def record(self, key: str, real: bool) -> None:
        (self.confirmed if real else self.false_positive).append(key)

    @property
    def adjudicated(self) -> int:
        return len(self.confirmed) + len(self.false_positive)

    @property
    def rate(self) -> float | None:
        if self.adjudicated == 0:
            return None
        return len(self.false_positive) / self.adjudicated

    def line(self) -> str:
        if self.rate is None:
            return ("false-positive rate: UNMEASURED (0 adjudicated) — an unmeasured "
                    "rate is not zero, and no norm may be promoted on it")
        return (f"false-positive rate: {self.rate:.0%} "
                f"({len(self.false_positive)}/{self.adjudicated} adjudicated)")


def gate_promotion(ledger: FPLedger, minimum: int = 5) -> tuple[bool, str]:
    """May a norm move from advise to enforce? Both halves must hold.

    A measured zero over two findings is not a soak. The sample floor is what stops a
    quiet week from being read as proof.
    """
    if ledger.rate is None:
        return False, "no adjudicated findings — nothing has been measured"
    if ledger.adjudicated < minimum:
        return False, (f"only {ledger.adjudicated} adjudicated, floor is {minimum} — "
                       f"a small sample of zeros is not a soak")
    if ledger.rate > 0:
        return False, f"false-positive rate is {ledger.rate:.0%}, not zero"
    return True, f"{ledger.adjudicated} adjudicated, 0 false positives"
