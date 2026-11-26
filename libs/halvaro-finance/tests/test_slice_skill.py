"""The skill of the finance slice inside the package (standard 3.7, issue #201, lane V, V5): generated from the docstrings, only the 15 functions, shipped in the wheel."""
import fnmatch
import re
import tomllib
from pathlib import Path


LIB = Path(__file__).resolve().parents[1]
SKILL = LIB / "src" / "halvaro" / "finance" / ".agents" / "skills" / "halvaro-finance"


def test_skill_md_has_the_open_format_header_and_names_the_folder():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\nname: (?P<name>[a-z0-9-]+)\ndescription: (?P<description>.+)\n---\n", text)
    assert m and m["name"] == SKILL.name and 20 < len(m["description"]) <= 1024
    assert "Use when" in m["description"] and "## When to use" in text


def test_pyproject_ships_every_skill_file_in_the_wheel():
    patterns = tomllib.loads((LIB / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["halvaro.finance"]
    base = LIB / "src" / "halvaro" / "finance"
    for p in SKILL.rglob("*.md"):
        rel = p.relative_to(base).as_posix()
        assert any(fnmatch.fnmatch(rel, pat) for pat in patterns), f"{rel} is not matched by package-data"
