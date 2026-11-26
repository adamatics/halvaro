"""Documentation gate of halvaro-esg (standard 3.1.1, 3.1.3, 3.2.5, 3.7.4; lane P3, #467): every public function has the use-this-when line, Args with every parameter, Returns, Raises, a
runnable Example and types. The rules are those of templates/lib/tests/test_docs_gate.py. The modules are brought to the gate in batches: DONE lists the modules whose every function passes, and
the test fails when a DONE module regresses or when a module passes the gate without being listed, so the list cannot go stale. When every module is listed, DONE is the whole package."""
from __future__ import annotations

import doctest
import importlib
import inspect
import pkgutil
import re

import halvaro.esg as lib

DONE: set[str] = {"activity", "audit_targets", "basis", "data_requests", "factors", "footprint", "ghg", "levers", "lines", "recompute", "score"}
SECTION = re.compile(r"^(Args|Returns|Raises|Example):\s*$", re.M)
PUBLIC = {n: getattr(lib, n) for n in lib.__all__ if inspect.isfunction(getattr(lib, n)) and hasattr(getattr(lib, n), "__halvaro__")}


def _module(fn) -> str:
    return fn.__module__.rsplit(".", 1)[1]


def doc_problems(name: str, fn) -> list[str]:
    """Everything that is missing in the documentation of one function; an empty list means it passes."""
    doc = inspect.getdoc(fn) or ""
    if not doc:
        return [f"{name}: no docstring"]
    out = []
    first = doc.splitlines()[0]
    if not (first.startswith("Use this when") and first.endswith(".")):
        out.append(f"{name}: the first line must be one sentence that starts with 'Use this when'")
    found = SECTION.findall(doc)
    out += [f"{name}: no {s} section" for s in ("Args", "Returns", "Raises", "Example") if s not in found]
    if "Example" in found and ">>>" not in doc:
        out.append(f"{name}: the Example has no >>> line, so it cannot run")
    sig = inspect.signature(fn)
    if "Args" in found:
        block = re.split(r"^(?:Returns|Raises|Example):\s*$", doc.split("Args:", 1)[1], flags=re.M)[0]
        out += [f"{name}: parameter {p} is not described in Args" for p in sig.parameters if not re.search(rf"^\s+{p}:", block, re.M)]
    out += [f"{name}: parameter {p.name} has no type" for p in sig.parameters.values() if p.annotation is p.empty]
    if sig.return_annotation is sig.empty:
        out.append(f"{name}: no return type")
    meta = getattr(fn, "__halvaro__", None)
    if meta is None:
        out.append(f"{name}: not registered with @function of halvaro.core.registry")
    elif meta.summary != first:
        out.append(f"{name}: the registry summary is not the first docstring line")
    return out


def test_every_function_of_a_done_module_passes_the_documentation_gate():
    modules = {_module(f) for f in PUBLIC.values()}
    assert DONE <= modules, f"DONE names modules that do not exist: {sorted(DONE - modules)}"
    problems = [p for n, f in PUBLIC.items() if _module(f) in DONE for p in doc_problems(n, f)]
    assert not problems, "\n".join(problems)


def test_a_module_that_passes_the_gate_is_listed_in_done():
    modules = {_module(f) for f in PUBLIC.values()}
    passing = sorted(m for m in modules - DONE if all(not doc_problems(n, f) for n, f in PUBLIC.items() if _module(f) == m))
    assert passing == [], f"add to DONE: {passing}"


def test_every_docstring_example_of_a_done_module_runs():
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
    seen = set()
    for info in pkgutil.iter_modules(lib.__path__, lib.__name__ + "."):
        if info.name.rsplit(".", 1)[1] not in DONE:
            continue
        module = importlib.import_module(info.name)
        for test in doctest.DocTestFinder(exclude_empty=True).find(module, info.name):
            runner.run(test)
            if test.examples:
                seen.add(test.name.rsplit(".", 1)[-1])
    result = runner.summarize(verbose=False)
    assert result.failed == 0, f"{result.failed} docstring example(s) fail"
    want = {n for n, f in PUBLIC.items() if _module(f) in DONE}
    assert want <= seen, f"no example in {sorted(want - seen)}"


def test_the_export_list_is_the_contract_every_public_function_of_the_package_is_exported():
    hidden = []
    for info in pkgutil.iter_modules(lib.__path__, lib.__name__ + "."):
        if info.name.rsplit(".", 1)[1].startswith("_"):
            continue                        # a private module (_guard, _util, _types): its names are private by the module
        module = importlib.import_module(info.name)
        for name, obj in vars(module).items():
            if inspect.isfunction(obj) and obj.__module__ == module.__name__ and not name.startswith("_") and name not in lib.__all__:
                hidden.append(f"{info.name}.{name}")
    assert hidden == [], f"public functions that are not in __all__ (export them or make them private with a leading _): {hidden}"


def test_the_gate_finds_what_is_missing():
    def no_doc(x):
        return x

    def bad(x: int) -> int:
        """Computes something.

        Args:
            y: not the parameter.
        """
        return x

    def untyped(x):
        """Use this when a test needs a function.

        Args:
            x: a value.

        Returns:
            x.

        Raises:
            nothing.

        Example:
            >>> 1
            1
        """
        return x
    assert doc_problems("f", no_doc) == ["f: no docstring"]
    text = " ".join(doc_problems("g", bad))
    assert "Use this when" in text and "no Returns" in text and "no Example" in text and "parameter x is not described" in text and "not registered" in text
    assert doc_problems("h", untyped) == ["h: parameter x has no type", "h: no return type", "h: not registered with @function of halvaro.core.registry"]
