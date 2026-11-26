"""The skill of the holiday functions inside the package (standard 3.7, issue #196, F5): generated from the docstrings, only the nine functions, shipped in the wheel."""
import fnmatch
import re
import tomllib
from pathlib import Path

import halvaro.hr as hr

LIB = Path(__file__).resolve().parents[1]
SKILL = LIB / "src" / "halvaro" / "hr" / ".agents" / "skills" / "halvaro-hr-holiday"
NINE = ("holiday_year_label", "holiday_year_bounds", "holiday_balance", "holiday_ledger", "carry_over_position", "carry_over_projection", "accrual_expected", "leave_vs_ledger", "high_carry_over")


def test_skill_md_has_the_open_format_header_and_names_the_folder():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\nname: (?P<name>[a-z0-9-]+)\ndescription: (?P<description>.+)\n---\n", text)
    assert m and m["name"] == SKILL.name and 20 < len(m["description"]) <= 1024
    assert "Use when" in m["description"] and "## When to use" in text


def test_only_the_nine_holiday_functions_are_described():
    pages = "\n".join(p.read_text(encoding="utf-8") for p in SKILL.rglob("*.md"))
    others = [n for n in hr.__all__ if n[0].islower() and n not in NINE and n != "__version__" and re.search(rf"\b{n}\b", pages)]
    assert not others, f"the skill names functions that are not holiday functions: {others}"


def test_pyproject_ships_every_skill_file_in_the_wheel():
    patterns = tomllib.loads((LIB / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["halvaro.hr"]
    base = LIB / "src" / "halvaro" / "hr"
    for p in SKILL.rglob("*.md"):
        rel = p.relative_to(base).as_posix()
        assert any(fnmatch.fnmatch(rel, pat) for pat in patterns), f"{rel} is not matched by package-data"
