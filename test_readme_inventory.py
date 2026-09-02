"""Keep the README's reader-facing skill inventory tied to the shipped tree."""

import re
from pathlib import Path


ROOT = Path(__file__).parent
README = ROOT / "README.md"
SKILLS = ROOT / "skills"


def shipped_skills() -> set[str]:
    return {
        path.name
        for path in SKILLS.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def documented_skills(readme: str) -> set[str]:
    section = readme.split("## 🧵 The Skills", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| [^|]*\*\*([a-z0-9-]+)\*\* \|", section, re.MULTILINE))


def test_readme_inventory_matches_shipped_skill_tree():
    readme = README.read_text(encoding="utf-8")
    shipped = shipped_skills()

    badge = re.search(r"shields\.io/badge/skills-(\d+)-", readme)
    assert badge, "README skill-count badge is missing"
    assert int(badge.group(1)) == len(shipped)
    assert f'alt="{len(shipped)} skills"' in readme
    assert documented_skills(readme) == shipped


def test_service_dependency_prose_uses_current_total():
    readme = README.read_text(encoding="utf-8")
    match = re.search(r"\*\*\w+ of the (\d+) skills want a service\*\*", readme)
    assert match, "README service-dependency summary is missing"
    assert int(match.group(1)) == len(shipped_skills())
