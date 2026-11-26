"""The skill of halvaro-delivery is shipped: the package data lists every file of the skill (standard 3.4.4, 3.5.2, 3.7.1, 3.7.2; lane P3, #439)."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
PKG = LIB / "src" / "halvaro" / "delivery"


def test_the_package_data_lists_every_file_of_the_skill():
    text = (LIB / "pyproject.toml").read_text(encoding="utf-8")
    globs = re.findall(r'"([^"]+)"', re.search(r'"halvaro\.delivery"\s*=\s*\[(.*?)\]', text, re.S).group(1))
    files = [str(p.relative_to(PKG)) for p in sorted((PKG / ".agents").rglob("*")) if p.is_file()]
    assert files and all(any(fnmatch.fnmatch(f, g) for g in globs) for f in files), [f for f in files if not any(fnmatch.fnmatch(f, g) for g in globs)][:5]
