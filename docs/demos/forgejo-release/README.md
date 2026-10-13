# Forgejo adapter demonstration

Recorded private API fixture, not an installed service or actual release.
Base `21759bfc12bb87520f62e5a85122cc85406a352d` has no adapter. Candidate
source introduces a conventional `feat` release plan: creates one three-file
release PR, then repeats with zero writes. The advanced-main negative refuses
before any additional write. This does not demonstrate hosted token authority,
review admission, native tag publication or alert clearance.

Reproduce: `python3 docs/demos/forgejo-release/reproduce.py`.
Replay the retained terminal recording:
`scriptreplay --log-out docs/demos/forgejo-release/output.log --log-timing docs/demos/forgejo-release/timing.log`.
The files are retained with the source PR; no inline playback is claimed.
The recording was inspected and replayed. Candidate identity is the commit
containing this caption and adapter; the committed fixture is unchanged by
base-only refreshes.
