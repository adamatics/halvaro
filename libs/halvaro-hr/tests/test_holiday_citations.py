"""Citations of the golden cases (standard 3.2, issue #196, F4): every cited id is in kb-dk-law-hr.ids, no legal number is typed in a case.

The id file is the list of the owner (the cloud session cannot read the knowledge base). `tools/check_citations.py --kb <bundle>` checks the same ids against a local copy of kb-dk-law-hr; it is not run in CI.
"""
import re
from pathlib import Path

import yaml

from halvaro.core import snapshot

LIB = Path(__file__).resolve().parents[1]
IDS = LIB / "tests" / "golden" / "kb-dk-law-hr.ids"
CASES = sorted((LIB / "tests" / "golden" / "holiday").glob("*.yaml"))
ID_RE = re.compile(r"dk/ferieloven/p-\d{4}[a-z]?")


def known_ids() -> dict:
    out = {}
    for line in IDS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ident, _, title = line.partition("|")
            out[ident.strip()] = title.strip()
    return out


def cases() -> list:
    return [(p.stem, yaml.safe_load(p.read_text(encoding="utf-8"))) for p in CASES]


def test_the_id_file_has_one_unique_id_with_a_title_per_line():
    lines = [ln for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == len(known_ids()) >= 40, "one id per line, no duplicates"
    assert all(ID_RE.fullmatch(i) and " | " in ln and t for ln in lines for i, t in [ (ln.split(" | ")[0], ln.split(" | ", 1)[1]) ]), "format: id | title"


def test_every_cited_id_is_in_the_id_file():
    ids = known_ids()
    for stem, case in cases():
        unknown = [c for c in case["cites"] if c not in ids]
        assert not unknown, f"{stem} cites {unknown}, which are not in kb-dk-law-hr.ids"


def _legal_numbers() -> set:
    facts = snapshot.load()["facts"]
    return {float(f["value"]) for i, f in facts.items() if i.startswith(("legal.DK.holiday.", "legal.DE.holiday.")) and isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool)} - {0.0, 1.0}


def _numbers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _numbers(v)
    elif isinstance(node, list):
        for v in node:
            yield from _numbers(v)


def test_no_legal_number_is_typed_in_a_case():
    legal = _legal_numbers()
    assert {2.08, 25.0} <= legal, "the holiday facts are read from the snapshot"
    for stem, case in cases():
        typed = sorted((set(_numbers(case["input"])) | set(_numbers(case["expect"]))) & legal)
        assert not typed, f"{stem}: number(s) {typed} equal a legal holiday fact: write fact('id') in a formula"
        text = f"{case['name']} {case.get('by_hand', '')}"
        words = {float(w) for w in re.findall(r"(?<![\w/.-])\d+(?:\.\d+)?(?![\w/-])", text)}
        assert not words & legal, f"{stem}: the name or by_hand text states {sorted(words & legal)}, which equals a legal holiday fact"
