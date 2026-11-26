"""Every entry of every behaviour-changes.yaml names functions that exist and have an oracle (lane P1, fallback). No release needed.

`check` reads the files only (no import of a library): the header fields of each entry, that its functions are in the code index of the library whose file it is in and
point to an oracle that exists, that its facts are in the core snapshot, and that ids are unique across the libraries. The tests run it on this repository and, on small
throwaway repositories, show that each kind of mistake is found."""
import ast
import copy
import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

FIELDS = {"id", "date", "functions", "facts", "kb", "before", "after", "class"}
CLASSES = {"correction", "policy change"}
SNAPSHOT = Path("libs/halvaro-core/src/halvaro/core/_data/snapshot.json")


def _defined(path: Path) -> set:
    """Names of the functions, methods and classes of a Python file (text only, nothing is imported)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _oracle_problem(repo: Path, lib: str, pointer: str) -> str | None:
    """None when the pointer is `py:<path>::<name>`, the path read from the library directory (tests/test_oracle_x.py of the four function libraries) or from build/ (../libs/halvaro-core/tests/... of core,
    halvaro_gen/... and tests/... of the generator for hr), the file is inside the repo and the name is defined in it; `none, ...` is no oracle."""
    if not isinstance(pointer, str) or not pointer.startswith("py:") or "::" not in pointer:
        return "has no oracle" if not pointer or str(pointer).startswith("none") else f"oracle {pointer!r} is not of the form py:<path>::<name>"
    rel, name = pointer[3:].split("::", 1)
    inside = [c for c in ((repo / "libs" / lib / rel).resolve(), (repo / "build" / rel).resolve()) if repo.resolve() in c.parents]
    if not inside:
        return f"oracle path {rel} leaves the repository"
    files = [c for c in inside if c.is_file()]
    if not files:
        return f"oracle file {rel} does not exist in libs/{lib} or in build"
    if not any(name.split(".")[-1] in _defined(c) for c in files):
        return f"oracle {name} is not defined in {rel}"
    return None


def check(repo: Path) -> tuple[list, int]:
    """(problems, number of entries read) for the behaviour-changes.yaml files under repo/libs."""
    problems, seen_ids, n = [], {}, 0
    snapshot = repo / SNAPSHOT
    facts = set(json.loads(snapshot.read_text(encoding="utf-8"))["facts"]) if snapshot.is_file() else set()
    for f in sorted((repo / "libs").glob("halvaro-*/behaviour-changes.yaml")):
        lib = f.parent.name
        short = lib.split("-", 1)[1]
        index = repo / "libs" / lib / "code-index.yaml"
        by_id = {e["id"]: e for e in yaml.safe_load(index.read_text(encoding="utf-8"))["functions"]} if index.is_file() else {}
        entries = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("changes")
        if not isinstance(entries, list):
            problems.append(f"{lib}: `changes` is not a list")
            continue
        for i, e in enumerate(entries):
            n += 1
            who = f"{lib} {e.get('id', f'entry {i}') if isinstance(e, dict) else f'entry {i}'}"
            if not isinstance(e, dict) or set(e) != FIELDS:
                problems.append(f"{who}: fields are {sorted(e) if isinstance(e, dict) else e!r}, expected {sorted(FIELDS)}")
                continue
            if not (isinstance(e["id"], str) and e["id"].startswith("BC-")):
                problems.append(f"{who}: id does not start with BC-")
            elif e["id"] in seen_ids:
                problems.append(f"{who}: id is also in {seen_ids[e['id']]}")
            seen_ids.setdefault(e["id"], lib)
            if not isinstance(e["date"], dt.date):
                problems.append(f"{who}: date is not an ISO date")
            if e["class"] not in CLASSES:
                problems.append(f"{who}: class is {e['class']!r}, expected correction or policy change")
            for k in ("before", "after"):
                if not (isinstance(e[k], str) and e[k].strip()):
                    problems.append(f"{who}: {k} is empty")
            for k in ("functions", "facts", "kb"):
                if not isinstance(e[k], list):
                    problems.append(f"{who}: {k} is not a list")
            if not isinstance(e["functions"], list):
                continue
            if not e["functions"]:
                problems.append(f"{who}: no function is named")
                continue
            for fid in e["functions"]:
                if not str(fid).startswith(f"halvaro.{short}."):
                    problems.append(f"{who}: {fid} is not a function of {lib}")
                elif fid not in by_id:
                    problems.append(f"{who}: {fid} is not in the code index of {lib}")
                else:
                    why = _oracle_problem(repo, lib, by_id[fid]["oracle"])
                    if why:
                        problems.append(f"{who}: {fid} {why}")
            for fact in e["facts"] if isinstance(e["facts"], list) else []:
                if fact not in facts:
                    problems.append(f"{who}: fact {fact} is not in the core snapshot")
    return problems, n


# ------------------------------------------------------------------ throwaway repository

GOOD_ENTRY = {"id": "BC-X-0001", "date": dt.date(2026, 11, 19), "functions": ["halvaro.x.mod.func"], "facts": ["policy.x.rule"], "kb": [],
              "before": "The function gave the old number.", "after": "The function gives the new number.", "class": "correction"}


def _write(repo: Path, entries: list, oracle: str = "py:../libs/halvaro-x/tests/test_oracle_mod.py::test_func_oracle", extra_lib: dict | None = None) -> None:
    """A repository with one library x: a code index with halvaro.x.mod.func, an oracle test file, the core snapshot with one fact and the behaviour file."""
    libs = {"halvaro-x": (entries, oracle)}
    libs.update(extra_lib or {})
    for lib, (ents, orc) in libs.items():
        short = lib.split("-", 1)[1]
        d = repo / "libs" / lib
        (d / "tests").mkdir(parents=True, exist_ok=True)
        (d / "tests" / "test_oracle_mod.py").write_text("def test_func_oracle():\n    '''halvaro.x.mod.func'''\n\nclass Builder:\n    def method(self):\n        pass\n", encoding="utf-8")
        (d / "code-index.yaml").write_text(yaml.safe_dump({"snapshot": "s", "functions": [{"id": f"halvaro.{short}.mod.func", "oracle": orc}]}), encoding="utf-8")
        (d / "behaviour-changes.yaml").write_text(yaml.safe_dump({"changes": ents}, sort_keys=False), encoding="utf-8")
    (repo / "build").mkdir(exist_ok=True)
    snap = repo / SNAPSHOT
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps({"facts": {"policy.x.rule": {}}}), encoding="utf-8")


def test_check_accepts_a_good_entry_and_counts_it(tmp_path):
    """check: an entry with every field, a function of its library that is in the code index with an oracle that exists, and a fact of the snapshot gives no problem and counts as one entry; a pointer to a method of a class,
    a path read from the library directory and a path read from build/ are found as well."""
    _write(tmp_path, [GOOD_ENTRY])
    assert check(tmp_path) == ([], 1)
    _write(tmp_path, [GOOD_ENTRY], oracle="py:../libs/halvaro-x/tests/test_oracle_mod.py::Builder.method")
    assert check(tmp_path) == ([], 1)
    _write(tmp_path, [GOOD_ENTRY], oracle="py:tests/test_oracle_mod.py::test_func_oracle")
    assert check(tmp_path) == ([], 1), "a path from the library directory"
    (tmp_path / "build" / "tests").mkdir()
    (tmp_path / "build" / "tests" / "test_gen.py").write_text("def test_generator():\n    pass\n", encoding="utf-8")
    _write(tmp_path, [GOOD_ENTRY], oracle="py:tests/test_gen.py::test_generator")
    assert check(tmp_path) == ([], 1), "a path from build/"
    _write(tmp_path, [])
    assert check(tmp_path) == ([], 0), "a library with no entry is fine"


def _edit(**kw):
    e = copy.deepcopy(GOOD_ENTRY)
    e.update(kw)
    return e


@pytest.mark.parametrize("entry, oracle, fragment", [
    (_edit(functions=["halvaro.x.mod.gone"]), None, "halvaro.x.mod.gone is not in the code index"),
    (_edit(functions=["halvaro.y.mod.func"]), None, "is not a function of halvaro-x"),
    (_edit(functions=[]), None, "no function is named"),
    (_edit(functions="halvaro.x.mod.func"), None, "functions is not a list"),
    (_edit(), "none, a constant with no result to check", "has no oracle"),
    (_edit(), "py:../libs/halvaro-x/tests/test_oracle_nowhere.py::test_func_oracle", "oracle file ../libs/halvaro-x/tests/test_oracle_nowhere.py does not exist in libs/halvaro-x or in build"),
    (_edit(), "py:../libs/halvaro-x/tests/test_oracle_mod.py::test_no_such_test", "test_no_such_test is not defined"),
    (_edit(), "py:../../../../../etc/passwd::x", "leaves the repository"),
    (_edit(), "oracle", "is not of the form"),
    (_edit(facts=["policy.x.other"]), None, "fact policy.x.other is not in the core snapshot"),
    (_edit(**{"class": "fix"}), None, "class is 'fix'"),
    (_edit(date="2026-11-19"), None, "date is not an ISO date"),
    (_edit(id="X-1"), None, "id does not start with BC-"),
    (_edit(before="  "), None, "before is empty"),
    (_edit(after=""), None, "after is empty"),
    (_edit(facts="policy.x.rule"), None, "facts is not a list"),
    (_edit(kb="KB-1"), None, "kb is not a list"),
])
def test_check_finds_each_kind_of_mistake(tmp_path, entry, oracle, fragment):
    """check: each of these mistakes in an otherwise good entry gives a problem naming it: an unknown function, a function of another library, no function, a none line instead of an oracle, a pointer to a missing file or test, a path outside the repo,
    a pointer of the wrong form, an unknown fact, a class that is no class, a date that is text, an id without the BC- start and an empty before or after text."""
    _write(tmp_path, [entry], **({"oracle": oracle} if oracle else {}))
    problems, n = check(tmp_path)
    assert n == 1 and len(problems) == 1 and fragment in problems[0], problems


def test_check_finds_a_missing_and_an_extra_field(tmp_path):
    """check: an entry without `kb` and an entry with an extra field are refused with the list of fields it expects, and are still counted."""
    short = {k: v for k, v in GOOD_ENTRY.items() if k != "kb"}
    _write(tmp_path, [short, dict(GOOD_ENTRY, id="BC-X-0002", note="x")])
    problems, n = check(tmp_path)
    assert n == 2 and len(problems) == 2 and all("expected" in p for p in problems), problems


def test_check_finds_an_id_used_in_two_libraries(tmp_path):
    """check: the same id in the file of two libraries is a problem named for the second one; two different ids are fine."""
    _write(tmp_path, [GOOD_ENTRY], extra_lib={"halvaro-y": ([dict(GOOD_ENTRY, functions=["halvaro.y.mod.func"])], "py:../libs/halvaro-y/tests/test_oracle_mod.py::test_func_oracle")})
    problems, n = check(tmp_path)
    assert n == 2 and len(problems) == 1 and "halvaro-y BC-X-0001: id is also in halvaro-x" in problems[0], problems
    _write(tmp_path, [GOOD_ENTRY], extra_lib={"halvaro-y": ([dict(GOOD_ENTRY, id="BC-Y-0001", functions=["halvaro.y.mod.func"])], "py:../libs/halvaro-y/tests/test_oracle_mod.py::test_func_oracle")})
    assert check(tmp_path) == ([], 2)


def test_check_finds_a_changes_key_that_is_not_a_list(tmp_path):
    """check: a behaviour file whose `changes` is not a list is a problem, and it counts no entry."""
    _write(tmp_path, [])
    (tmp_path / "libs" / "halvaro-x" / "behaviour-changes.yaml").write_text("changes: {}\n", encoding="utf-8")
    assert check(tmp_path) == (["halvaro-x: `changes` is not a list"], 0)


def test_check_finds_an_entry_that_is_no_mapping_and_a_library_without_a_code_index(tmp_path):
    """check: an entry that is a number instead of a mapping is refused with its fields named and counted; a library with a behaviour file and no code-index.yaml reports its function as not in the index."""
    _write(tmp_path, [5])
    problems, n = check(tmp_path)
    assert n == 1 and len(problems) == 1 and "fields are" in problems[0], problems
    _write(tmp_path, [GOOD_ENTRY])
    (tmp_path / "libs" / "halvaro-x" / "code-index.yaml").unlink()
    problems, n = check(tmp_path)
    assert n == 1 and len(problems) == 1 and "not in the code index" in problems[0], problems
