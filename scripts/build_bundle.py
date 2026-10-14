#!/usr/bin/env python3
"""Build a reproducible skill bundle from one committed Git revision.

This is a local packaging step. It creates no tag, release, or installation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*)?")
MAX_BYTES = 32 * 1024 * 1024


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    ).stdout


def build_bundle(root: Path, ref: str, output: Path, expected_version: str | None = None) -> dict:
    if not ref or ref.startswith("-"):
        raise ValueError("invalid revision")
    revision = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    records = []
    total = 0
    for row in git(root, "ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if path not in {"README.md", "LICENSE", "version.txt"} and not path.startswith("skills/"):
            continue
        mode, kind, oid = metadata.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"bundle requires regular files: {path}")
        if path.startswith("/") or any(part in {".", ".."} for part in PurePosixPath(path).parts):
            raise ValueError("unsafe bundle path")
        size = int(git(root, "cat-file", "-s", oid))
        total += size
        if total > MAX_BYTES:
            raise ValueError("bundle exceeds 32 MiB source limit")
        data = git(root, "cat-file", "blob", oid)
        records.append((path, int(mode, 8) & 0o777, data))
    records.sort(key=lambda record: record[0])
    files = {path: data for path, _, data in records}
    for required in ("README.md", "LICENSE", "version.txt"):
        if required not in files:
            raise ValueError(f"missing committed {required}")
    if not any(path.startswith("skills/") and path.endswith("/SKILL.md") for path in files):
        raise ValueError("no committed skill inventory")
    version = files["version.txt"].decode().strip()
    if not VERSION.fullmatch(version):
        raise ValueError("invalid committed version")
    if expected_version is not None and expected_version.removeprefix("v") != version:
        raise ValueError("release version differs from committed version")
    manifest = {
        "format_version": 1,
        "version": version,
        "source_revision": revision,
        "files": [
            {"path": path, "mode": mode, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for path, mode, data in records
        ],
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    prefix = f"skein-{version}"
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path, mode, data in [*records, ("bundle.json", 0o644, manifest_bytes)]:
            member = tarfile.TarInfo(f"{prefix}/{path}")
            member.size, member.mode, member.mtime = len(data), mode, 0
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            archive.addfile(member, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
        stream.write(raw_tar.getvalue())
    name = f"{prefix}.tar.gz"
    payload = compressed.getvalue()
    assets = {
        name: payload,
        "SHA256SUMS": f"{hashlib.sha256(payload).hexdigest()}  {name}\n".encode(),
        "bundle.json": manifest_bytes,
    }
    output.mkdir(parents=True, exist_ok=True)
    # Preflight every destination before writing any asset; never replace a release.
    for asset, data in assets.items():
        target = output / asset
        if target.is_symlink() or (target.exists() and target.read_bytes() != data):
            raise ValueError(f"different asset already exists: {asset}")
    for asset, data in assets.items():
        target = output / asset
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(data)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    manifest = build_bundle(args.repo, args.ref, args.output, args.expected_version)
    print(json.dumps({"version": manifest["version"], "source_revision": manifest["source_revision"], "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
