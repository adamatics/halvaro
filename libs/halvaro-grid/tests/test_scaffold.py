"""Packaging and the registry state of the package."""
import ast
from pathlib import Path


import halvaro.grid as grid
from halvaro.core import registry

SRC = Path(grid.__file__).parent
LIB = Path(__file__).resolve().parents[1]


def test_namespace_package_and_marker_files():
    assert not (SRC.parent / "__init__.py").exists(), "halvaro must stay a PEP 420 namespace package"
    assert (SRC / "py.typed").exists()
    assert set(grid.__all__) <= set(dir(grid)) and grid.__version__ == "0.1.0"


def test_import_does_no_io_and_reads_no_environment_clock_or_network():
    banned_calls = {("os", "environ"), ("os", "getenv"), ("datetime", "now"), ("datetime", "utcnow"), ("date", "today"), ("time", "time"),
                    ("Timestamp", "now"), ("Timestamp", "today"), ("np", "random"), ("numpy", "random")}
    banned_modules = {"socket", "urllib", "requests", "http", "subprocess"}
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Attribute):
                owner = node.value.attr if isinstance(node.value, ast.Attribute) else getattr(node.value, "id", None)
                assert (owner, node.attr) not in banned_calls, f"{f.name}: {owner}.{node.attr}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not {n.split(".")[0] for n in names} & banned_modules, f"{f.name}: imports {names}"


def test_registry_check_is_clean():
    assert registry.check() == []


def test_dependency_on_core_is_declared_with_an_upper_bound():
    text = (LIB / "pyproject.toml").read_text()
    assert 'halvaro-core>=0.1,<0.2' in text and "pandas>=2.0,<3" in text
