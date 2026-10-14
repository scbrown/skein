# Skill bundles

The initial `version.txt` value, `0.0.0`, is an unpublished baseline. A release
PR must change it before the first published bundle. Installing or publishing
is a separate operation from building an archive.

Build from the immutable commit selected by a reviewed release PR:

```sh
python3 scripts/build_bundle.py --ref <commit-or-tag> --expected-version v0.1.0 --output dist
```

The committed version must match the requested release version. The builder
reads Git objects, so dirty files and untracked files are excluded. It includes
the committed `skills/` inventory, README, license, and version file, preserves
executable modes, and refuses symlinks and submodules in the inventory.

Outputs are `skein-<version>.tar.gz`, `SHA256SUMS`, and `bundle.json`. The archive
also contains the manifest, which records the source commit, version, and every
packaged file's path, mode, size, and SHA-256. Archive timestamps and ownership
are normalized so the same committed source produces the same bytes. Different
existing assets are refused; identical assets are an unchanged result.

Before installing, verify `SHA256SUMS` and inspect the recorded version and
source commit. Keep the previous verified bundle for rollback. Copy only the
desired skill directories using the install procedure in the README.

The builder does not create tags, releases, release PRs, or installations.
Publication must come from a merged, independently reviewed release PR and a
successful publisher run. The working repository and its public mirror have
different histories: public publication must preserve the forward-only,
scrubbed mirror protocol. A GitHub release alone does not establish a Forgejo
release or resolve a Forgejo release-health finding.

## Forgejo release PR lane

After successful main-push tests, the Forgejo workflow runs
`scripts/forgejo_release.py --execute` with its automatic repository token.
It computes a stable version from conventional commits (`fix`/`perf` patch,
`feat` minor, breaking changes major or minor before 1.0), creates one
`release-pr/<version>` proposal, and reads back its exact plan. The proposal
contains only `version.txt`, `CHANGELOG.md` and `release-plan.json`.
An unchanged proposal is read-only. An advanced proposal, orphan branch,
truncated inventory, redirect or indeterminate write stops for reconciliation;
the adapter never retries a write blindly or merges a PR.

The generated release PR still needs complete current CI and one independent
review through the repository's governed bot-release admission route. Workflow
eligibility is not that review. A changed proposal needs new review; a base
refresh can reuse review only when the trusted helper proves identical content.
Do not substitute a human source author to make a generated PR admissible.

On the exact merged release revision, the same successful main-push lane checks
the proposal's repository, marker, three paths and committed source plan. It
builds the immutable bundle, creates and reads back its tag, uploads assets to
a draft release, downloads each for byte comparison, then publishes the draft.
The plan's source must equal the merged commit's first parent, so a base
refresh that introduces unplanned changes refuses before building or tagging.
Refresh the release plan and obtain its normal current CI and review first.
Wrong tags, corrupt assets or newer releases refuse publication. Tokens are
automatic workflow credentials, never command-line arguments or log output.
Pull-request and manually dispatched runs cannot invoke the publisher.

The GitHub mirror runs tests only. Its forward-only scrubbed projection remains
a separate governed operation; never push the primary repository's raw history
or tag to bypass that seam. Release adoption is proven only by the native
published version, matching source and verified bundle assets, followed by the
scheduled release-health clear. Rollback uses the previous verified bundle;
publisher changes are reverted through another reviewed source PR.
