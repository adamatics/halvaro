"""Packaging, index and the stamping workaround for core's export_index."""
import ast
from pathlib import Path


import halvaro.hr as hr

SRC = Path(hr.__file__).parent
LIB = Path(__file__).resolve().parents[1]


def test_namespace_package_and_marker_files():
    assert not (SRC.parent / "__init__.py").exists(), "halvaro must stay a PEP 420 namespace package"
    assert (SRC / "py.typed").exists()
    assert set(hr.__all__) <= set(dir(hr))


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


# Functions that read Month 12 sources: it-assets (resolve_assignments) and competence (every certs function).
MONTH12_FUNCTIONS = {"halvaro.hr.crosswalk.resolve_assignments", "halvaro.hr.pay.with_education", "halvaro.hr.pay.education_explained_share",
                      "halvaro.hr.staffing.experience_summary", "halvaro.hr.staffing.planned_vs_actual_hours", "halvaro.hr.availability.utilisation",
                      "halvaro.hr.controlled.controlled_work_audit"}    # competence, projects and it-assets sources
MONTH12_MODULES = {"certs", "coverage"}
