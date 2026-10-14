#!/usr/bin/env python3
"""Forgejo-native release PRs and immutable release publication.

Only a successful main-push workflow may execute writes. This adapter never
merges a PR: complete CI and independent review remain outside the publisher.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from build_bundle import build_bundle, git


MARKER = "[forgejo-release:v1]"
FILES = {"version.txt", "CHANGELOG.md", "release-plan.json"}
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
SHA = re.compile(r"[0-9a-f]{40}")


class Refusal(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    if not SEMVER.fullmatch(value):
        raise Refusal("expected a stable semantic version")
    return tuple(map(int, value.split(".")))


def release_plan(previous: str, source: str, commits: list[tuple[str, str]]) -> dict | None:
    """Compute a version from conventional commits; ordinary prose is not a bump."""
    major, minor, patch = version_tuple(previous)
    if not SHA.fullmatch(source):
        raise Refusal("invalid source revision")
    level = 0
    entries = []
    for revision, message in commits:
        if not SHA.fullmatch(revision):
            raise Refusal("invalid changelog revision")
        subject = message.splitlines()[0] if message.splitlines() else ""
        match = re.fullmatch(r"([a-z]+)(?:\([^\n]+\))?(!)?: (.+)", subject)
        if not match:
            continue
        breaking = bool(match[2]) or bool(re.search(r"^BREAKING[ -]CHANGE:\s", message, re.M))
        kind = match[1]
        current = 3 if breaking else (2 if kind == "feat" else (1 if kind in {"fix", "perf"} else 0))
        level = max(level, current)
        if current:
            entries.append({"revision": revision, "subject": subject})
    if not level:
        return None
    if level == 3 and major:
        major, minor, patch = major + 1, 0, 0
    elif level >= 2:
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return {"schema": 1, "previous_version": previous, "version": f"{major}.{minor}.{patch}",
            "source_revision": source, "commits": entries}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal("unexpected API redirect")


class Forgejo:
    def __init__(self, server: str, repository: str, token: str):
        parsed = urllib.parse.urlsplit(server)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.query:
            raise Refusal("invalid Forgejo server")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
            raise Refusal("repository and automatic workflow token are required")
        self.server, self.repository, self.token = server.rstrip("/"), repository, token
        self.base = f"{self.server}/api/v1/repos/{repository}"
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, path: str, method: str = "GET", data=None, *, missing=False, binary=False, content_type=None):
        url = path if urllib.parse.urlsplit(path).scheme else self.base + ("/" + path if path else "")
        if urllib.parse.urlsplit(url)[:2] != urllib.parse.urlsplit(self.server)[:2]:
            raise Refusal("cross-origin asset URL")
        payload = data if isinstance(data, bytes) else (json.dumps(data).encode() if data is not None else None)
        headers = {"Authorization": "token " + self.token, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = content_type or "application/json"
        try:
            with self.opener.open(urllib.request.Request(url, payload, headers, method=method), timeout=60) as response:
                raw = response.read(40 * 1024 * 1024 + 1)
                if len(raw) > 40 * 1024 * 1024:
                    raise Refusal("oversized API result")
                return raw if binary else json.loads(raw)
        except urllib.error.HTTPError as error:
            if method == "GET" and missing and error.code == 404:
                return None
            raise Refusal(f"Forgejo {method} HTTP {error.code}; outcome may be indeterminate") from None
        except (OSError, ValueError) as error:
            raise Refusal(f"Forgejo {method} {type(error).__name__}; preserve outcome before retry") from None

    def listing(self, path: str) -> list:
        result = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 21):
            batch = self.request(f"{path}{separator}limit=50&page={page}")
            if not isinstance(batch, list):
                raise Refusal("unexpected list result")
            result.extend(batch)
            if len(batch) < 50:
                return result
        raise Refusal("truncated inventory")


def committed(root: Path, revision: str, path: str) -> bytes:
    return git(root, "show", f"{revision}:{path}")


def plan_from_git(root: Path, source: str) -> dict | None:
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise Refusal("complete history required")
    previous = committed(root, source, "version.txt").decode().strip()
    version_tuple(previous)
    if previous == "0.0.0":
        selection = source
    else:
        tag = "refs/tags/v" + previous
        git(root, "rev-parse", "--verify", f"{tag}^{{commit}}")
        git(root, "merge-base", "--is-ancestor", tag, source)
        selection = f"{tag}..{source}"
    parts = git(root, "log", "--reverse", "--format=%H%x00%B%x00", selection).decode().split("\0")
    commits = [(parts[index].strip(), parts[index + 1]) for index in range(0, len(parts) - 1, 2)]
    return release_plan(previous, source, commits)


def propose(api: Forgejo, root: Path, source: str) -> dict:
    plan = plan_from_git(root, source)
    if plan is None:
        return {"state": "no-release-change"}
    remote = api.request("branches/main")
    if remote["commit"]["id"] != source:
        raise Refusal("main advanced; wait for its own workflow")
    branch = "release-pr/" + plan["version"]
    matches = [p for p in api.listing("pulls?state=open") if p["head"]["ref"] == branch]
    if len(matches) > 1:
        raise Refusal("duplicate release PRs")
    if matches:
        # Updating proposal content must produce new CI/review; never pretend
        # a stale immutable proposal includes newly arrived commits.
        current = api.request("contents/release-plan.json?ref=" + urllib.parse.quote(branch, safe=""))
        existing = json.loads(base64.b64decode(current["content"]))
        if existing != plan:
            raise Refusal("existing release PR needs a normal base/content refresh")
        return {"state": "existing", "number": matches[0]["number"]}
    if api.request("branches/" + urllib.parse.quote(branch, safe=""), missing=True) is not None:
        raise Refusal("unowned or indeterminate release branch exists; reconcile before retry")
    changes = {
        "version.txt": (plan["version"] + "\n").encode(),
        "release-plan.json": (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode(),
    }
    changelog = api.request("contents/CHANGELOG.md?ref=" + source, missing=True)
    old = base64.b64decode(changelog["content"]).decode() if changelog else "# Changelog\n"
    notes = "\n".join(f"- {entry['subject']} ({entry['revision'][:12]})" for entry in plan["commits"])
    changes["CHANGELOG.md"] = (f"# Changelog\n\n## {plan['version']}\n\n{notes}\n\n" + old.removeprefix("# Changelog\n")).encode()
    operations = []
    for path, data in sorted(changes.items()):
        current = api.request("contents/" + path + "?ref=" + source, missing=True)
        operation = {"path": path, "operation": "update" if current else "create", "content": base64.b64encode(data).decode()}
        if current:
            operation["sha"] = current["sha"]
        operations.append(operation)
    api.request("branches", "POST", {"old_ref_name": source, "new_branch_name": branch})
    if api.request("branches/" + urllib.parse.quote(branch, safe=""))["commit"]["id"] != source:
        raise Refusal("new branch does not match the pinned main source")
    api.request("contents", "POST", {"branch": branch, "files": operations,
                                     "message": f"chore(release): {plan['version']}"})
    observed = api.request("contents/release-plan.json?ref=" + urllib.parse.quote(branch, safe=""))
    if json.loads(base64.b64decode(observed["content"])) != plan:
        raise Refusal("release branch readback differs")
    created = api.request("pulls", "POST", {"base": "main", "head": branch,
                          "title": f"chore(release): {plan['version']}",
                          "body": f"{MARKER}\nSource: {source}\nVersion: {plan['version']}\n\nComplete current CI and ONE independent review are required. This workflow never merges its own PR."})
    observed = api.request(f"pulls/{created['number']}")
    if observed["head"]["ref"] != branch or observed["base"]["ref"] != "main":
        raise Refusal("release PR readback differs")
    return {"state": "created", "number": observed["number"]}


def admitted_release(pr: dict, repository: str, revision: str, plan: dict, paths: set[str]) -> None:
    version_tuple(plan["version"])
    if (not pr.get("merged") or pr.get("merge_commit_sha") != revision
            or pr["base"]["ref"] != "main" or pr["head"]["ref"] != "release-pr/" + plan["version"]
            or pr["head"]["repo"]["full_name"] != repository
            or MARKER not in (pr.get("body") or "") or paths != FILES):
        raise Refusal("not an exact merged release PR")


def publish(api: Forgejo, root: Path, revision: str, output: Path) -> dict | None:
    matches = [p for p in api.listing("pulls?state=closed") if p.get("merged") and p.get("merge_commit_sha") == revision]
    candidates = [p for p in matches if MARKER in (p.get("body") or "")]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise Refusal("ambiguous merged release")
    pr = candidates[0]
    plan = json.loads(committed(root, revision, "release-plan.json"))
    paths = {x["filename"] for x in api.listing(f"pulls/{pr['number']}/files")}
    admitted_release(pr, api.repository, revision, plan, paths)
    if api.request("branches/main")["commit"]["id"] != revision:
        raise Refusal("main advanced; reconcile the merged release before publication")
    source = plan["source_revision"]
    if not SHA.fullmatch(source) or plan_from_git(root, source) != plan:
        raise Refusal("release plan does not match committed source history")
    parents = git(root, "rev-list", "--parents", "-n", "1", revision).decode().split()
    if len(parents) not in {2, 3} or parents[0] != revision or parents[1] != source:
        raise Refusal("release plan is stale against the merged main base; refresh the proposal")
    git(root, "merge-base", "--is-ancestor", source, revision)
    manifest = build_bundle(root, revision, output, plan["version"])
    assets = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    archive = f"skein-{manifest['version']}.tar.gz"
    if set(assets) != {archive, "SHA256SUMS", "bundle.json"}:
        raise Refusal("unexpected package assets")
    tag = "v" + plan["version"]
    existing = api.request("tags/" + tag, missing=True)
    if existing is None:
        api.request("tags", "POST", {"tag_name": tag, "target": revision})
        existing = api.request("tags/" + tag)
    if existing["commit"]["sha"] != revision:
        raise Refusal("tag resolves to a different source")
    release = api.request("releases/tags/" + tag, missing=True)
    if release is None:
        release = api.request("releases", "POST", {"tag_name": tag, "target_commitish": revision,
                                                  "name": tag, "draft": True, "body": f"Merged release PR #{pr['number']}. Source {revision}."})
    release_id = release["id"]
    for name, data in sorted(assets.items()):
        present = [x for x in api.listing(f"releases/{release_id}/assets") if x["name"] == name]
        if len(present) > 1:
            raise Refusal("duplicate release asset")
        if not present:
            if not release.get("draft"):
                raise Refusal("published release is missing assets; do not mutate it")
            boundary = "bundle-" + hashlib.sha256(data).hexdigest()
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="attachment"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                    + data + f"\r\n--{boundary}--\r\n".encode())
            api.request(f"releases/{release_id}/assets?name=" + urllib.parse.quote(name), "POST", body,
                        content_type="multipart/form-data; boundary=" + boundary)
            present = [x for x in api.listing(f"releases/{release_id}/assets") if x["name"] == name]
        if len(present) != 1 or api.request(present[0]["browser_download_url"], binary=True) != data:
            raise Refusal("release asset readback differs")
    for newer in api.listing("releases"):
        if not newer.get("draft") and not newer.get("prerelease") and newer["tag_name"].startswith("v"):
            if version_tuple(newer["tag_name"][1:]) > version_tuple(plan["version"]):
                raise Refusal("a newer release is already published")
    if release.get("draft"):
        api.request(f"releases/{release_id}", "PATCH", {"draft": False})
    observed = api.request(f"releases/{release_id}")
    if observed.get("draft") or observed["tag_name"] != tag:
        raise Refusal("published release readback differs")
    return {"state": "published", "tag": tag, "revision": revision, "release_id": release_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    source = git(args.repo, "rev-parse", "HEAD").decode().strip()
    if not args.execute:
        print(json.dumps({"plan": plan_from_git(args.repo, source), "writes": False}))
        return
    if (os.environ.get("FORGEJO_EVENT_NAME") != "push" or os.environ.get("FORGEJO_REF") != "refs/heads/main"
            or os.environ.get("FORGEJO_SHA") != source):
        raise Refusal("writes require the exact successful main-push workflow")
    api = Forgejo(os.environ["FORGEJO_SERVER_URL"], os.environ["FORGEJO_REPOSITORY"], os.environ["FORGEJO_TOKEN"])
    result = publish(api, args.repo, source, args.output)
    if result is None:
        result = propose(api, args.repo, source)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, ValueError, subprocess.CalledProcessError, KeyError) as error:
        print("REFUSED: " + (str(error) if isinstance(error, Refusal) else type(error).__name__))
        raise SystemExit(2)
