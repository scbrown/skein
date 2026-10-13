import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("build_bundle", Path(__file__).with_name("build_bundle.py"))
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.output = Path(self.temp.name) / "out"
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for name, data in {"version.txt": "0.1.0\n", "LICENSE": "MIT\n", "README.md": "Skills\n", "skills/example/SKILL.md": "A skill\n", "skills/example/run.py": "print('example')\n"}.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        (self.root / "skills/example/run.py").chmod(0o755)
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True).stdout.decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def test_inventory_checksum_and_executable_mode(self):
        manifest = bundle.build_bundle(self.root, "HEAD", self.output, "v0.1.0")
        archive = self.output / "skein-0.1.0.tar.gz"
        self.assertEqual((self.output / "SHA256SUMS").read_text(), f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        self.assertEqual(manifest["source_revision"], self.git("rev-parse", "HEAD"))
        with tarfile.open(archive) as tar:
            self.assertEqual(tar.getmember("skein-0.1.0/skills/example/run.py").mode, 0o755)
            self.assertEqual(json.load(tar.extractfile("skein-0.1.0/bundle.json")), manifest)
            self.assertEqual(len(tar.getmembers()), len(manifest["files"]) + 1)

    def test_committed_revision_ignores_dirty_and_untracked_files(self):
        bundle.build_bundle(self.root, "HEAD", self.output)
        original = (self.output / "skein-0.1.0.tar.gz").read_bytes()
        (self.root / "skills/example/SKILL.md").write_text("dirty\n")
        (self.root / "skills/example/private.txt").write_text("untracked\n")
        other = self.output.parent / "other"
        bundle.build_bundle(self.root, "HEAD", other)
        self.assertEqual(original, (other / "skein-0.1.0.tar.gz").read_bytes())

    def test_reproducible_idempotent_bytes(self):
        bundle.build_bundle(self.root, "HEAD", self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        bundle.build_bundle(self.root, "HEAD", self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_symlink_refuses_without_assets(self):
        (self.root / "skills/example/link").symlink_to("/etc/passwd")
        self.commit()
        with self.assertRaisesRegex(ValueError, "regular files"):
            bundle.build_bundle(self.root, "HEAD", self.output)
        self.assertFalse(self.output.exists())

    def test_release_tag_version_mismatch_refuses(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            bundle.build_bundle(self.root, "HEAD", self.output, "v0.2.0")
        self.assertFalse(self.output.exists())

    def test_existing_different_asset_refuses_before_other_writes(self):
        self.output.mkdir()
        (self.output / "SHA256SUMS").write_text("different\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            bundle.build_bundle(self.root, "HEAD", self.output)
        self.assertEqual([p.name for p in self.output.iterdir()], ["SHA256SUMS"])

    def test_missing_skill_inventory_refuses(self):
        self.git("rm", "-r", "skills")
        self.git("commit", "-qm", "remove skills")
        with self.assertRaisesRegex(ValueError, "inventory"):
            bundle.build_bundle(self.root, "HEAD", self.output)


if __name__ == "__main__":
    unittest.main()
