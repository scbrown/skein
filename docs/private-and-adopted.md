# What stays private, and the adopted-pack licence position

## Adopted packs: Trail of Bits skills (tob-*)

Our agents run 12 `tob-*` skills adopted from Trail of Bits'
[skills repository](https://github.com/trailofbits/skills). **They are not
republished here, deliberately.** The upstream licence is
**CC-BY-SA-4.0** (verified 2026-07-23 against the upstream repo): redistribution
is permitted with attribution and ShareAlike, but vendoring a copyleft subtree
into this MIT repo would (a) put two licences in one tree, (b) bind every
derivative of those files to CC-BY-SA, and (c) create a drift-prone copy of a
pack the authors actively maintain. Adopt them from upstream — that is the
whole point of the pattern this repo exists to serve, in the other direction.

## Skills that stay private, and why

Three of our skills are deliberately not here:

| skill | why it stays private |
|---|---|
| `homelab-po` | Product-owner process bound to our tracker, our rig topology, and our escalation paths. The generic idea it embodies — a backlog-grooming discipline — is not separable from our nouns without becoming an empty template. |
| `assign-work` | Dispatch mechanics for our specific coordination stack. Its portable core — how to hand work to another agent honestly — **is already here, generalized, as `dispatch-work`** (this repo's flagship). Publishing both would ship one idea twice, one copy welded to tools you don't have. |
| `graph-capture` | A session-stop hook soliciting knowledge-graph episodes against our ontology and our graph server's shape registry. Generalizable in principle (a "capture what you learned" stop-hook is a good pattern); nobody has done that work yet. If you want it, open an issue — the private version is the design sketch. |

The test for publication is the repo's standing acceptance: a skill copied out
of this repo into a clean agent with no context from our environment must RUN.
These three fail that test by construction; renaming their nouns would make
them lie about it instead of failing it.
