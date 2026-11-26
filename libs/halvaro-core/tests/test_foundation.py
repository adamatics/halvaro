"""C0: packaging, snapshot, errors, Envelope, registry."""
import ast
import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

import halvaro.core as core
from halvaro.core import registry

SRC = Path(core.__file__).parent


def test_namespace_package_and_marker_files():
    assert not (SRC.parent / "__init__.py").exists(), "halvaro must be a PEP 420 namespace package"
    assert (SRC / "py.typed").exists()
    assert set(core.__all__) <= set(dir(core)), "every name of __all__ is defined"


def test_import_does_no_io_and_reads_no_environment_clock_or_network():
    banned_calls = {("os", "environ"), ("os", "getenv"), ("datetime", "now"), ("datetime", "utcnow"), ("date", "today"), ("time", "time")}
    banned_modules = {"socket", "urllib", "requests", "http", "subprocess"}
    for f in SRC.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Attribute):
                owner = node.value.attr if isinstance(node.value, ast.Attribute) else getattr(node.value, "id", None)
                assert (owner, node.attr) not in banned_calls, f"{f.name}: {owner}.{node.attr}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not {n.split(".")[0] for n in names} & banned_modules, f"{f.name}: imports {names}"
    code = "import halvaro.core as c; from halvaro.core import snapshot; print(snapshot.load.cache_info().currsize)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONPATH": str(SRC.parents[1])}, check=True)
    assert out.stdout.strip() == "0", "the snapshot must not be loaded by importing the package"


def test_errors_name_what_where_and_what_to_do():
    e = core.StageRefusal(["finance"], "month3", "day1", "halvaro.hr.pay.x")
    assert "finance" in str(e) and "month3" in str(e) and "day1" in str(e) and "Ask" in str(e)
    assert core.RestrictedColumnRefusal("hr.employment_term.base_salary", "mcp_people", "day1").column.endswith("base_salary")
    assert isinstance(core.FactNotFound("x"), KeyError) and str(core.FactNotFound("nope")) == "nope"
    assert all(issubclass(getattr(core, n), core.HalvaroError) for n in core.__all__ if n.endswith(("Error", "Refusal", "Mismatch", "Keys", "Key", "Region", "Missing")))


def test_envelope_is_the_one_result_type_and_subclasses_keep_every_field():
    base = [f.name for f in dataclasses.fields(core.Envelope)]
    assert base == ["value", "facts_used", "status", "as_of", "stage", "sources", "basis", "synthetic", "warnings", "function", "library_version", "snapshot", "release"]

    @dataclasses.dataclass(frozen=True)
    class Provenance(core.Envelope):
        factor_sets: tuple = ()

    sub = [f.name for f in dataclasses.fields(Provenance)]
    assert sub[:len(base)] == base and sub[-1] == "factor_sets"


def test_make_envelope_stamps_provenance():
    f = [core.fact("legal.DK.holiday.annual_days"), core.fact("world.fx_eur_dkk_fixed")]
    env = core.make_envelope(25, "halvaro.core.facts.fact", facts=f, sources=("hr.employee.emp_key", "finance.cost_centre.cc_key"))
    assert env.status == "VERIFY" and env.stage == "month3" and env.synthetic is True
    assert env.function == "halvaro.core.facts.fact" and env.snapshot == core.snapshot_hash() and env.library_version == core.__version__
    assert env.facts_used[0][0] == "legal.DK.holiday.annual_days"
    assert core.make_envelope(1, facts=[core.fact("world.fx_eur_dkk_fixed")]).status == "ok"


def test_registry_index_is_sorted_deterministic_and_valid():
    a, b = registry.export_index(), registry.export_index()
    assert a == b and [r["id"] for r in a] == sorted(r["id"] for r in a)
    assert len(a) >= 40 and all(r["id"].startswith("halvaro.core.") for r in a)
    jsonschema = pytest.importorskip("jsonschema")
    schema = registry.index_schema()
    for r in a:
        jsonschema.validate(r, schema)


def test_registry_derives_stage_from_sources_and_checks_ids():
    by = {r["id"]: r for r in registry.export_index()}
    assert by["halvaro.core.org.check_org_integrity"]["stage"] == "day1"
    assert by["halvaro.core.keys.parse_key"]["stage"] is None
    assert registry.check() == []

    @registry.function(facts=("no.such.fact",), sources=("hr.employee.nope",), tags=("x1",), deprecated="halvaro.core.nope")
    def _probe():
        """A probe."""

    try:
        problems = registry.check()
        assert len(problems) == 4 and all("_probe" in p for p in problems)
    finally:
        registry._REGISTRY.pop(_probe.__halvaro__.id)
    with pytest.raises(ValueError):
        registry.function(id="halvaro.core.keys.parse_key")(lambda: None)


def test_registry_writes_the_index_file(tmp_path):
    import yaml
    registry.export_index(tmp_path / "code-index.yaml")
    doc = yaml.safe_load((tmp_path / "code-index.yaml").read_text())
    assert doc["snapshot"] == core.snapshot_hash() and len(doc["functions"]) == len(registry.registered())


@pytest.fixture
def fake_library(monkeypatch):
    """A registered function of an imaginary distribution halvaro-fake (source tree version 9.9.9) and a decoy of halvaro-fakex."""
    import types
    monkeypatch.setitem(sys.modules, "halvaro.fake._version", types.SimpleNamespace(__version__="9.9.9"))

    @registry.function(id="halvaro.fake.mod.probe", sources=("hr.employee.emp_key",), tags=("T0",))
    def probe():
        """A probe of the fake distribution."""

    @registry.function(id="halvaro.fakex.mod.other")
    def other():
        """A decoy whose prefix starts like the fake one."""

    yield probe
    registry._REGISTRY.pop("halvaro.fake.mod.probe", None)
    registry._REGISTRY.pop("halvaro.fakex.mod.other", None)


def test_library_prefix_and_library_of():
    assert registry.library_prefix("halvaro-hr") == "halvaro.hr." and registry.library_of("halvaro.hr.org.terms_on") == "halvaro-hr"
    assert registry.library_of("halvaro.core.keys.parse_key") == "halvaro-core"
    for bad in ("terms_on", "halvaro.hr.terms_on", "other.hr.org.f"):
        with pytest.raises(core.HalvaroError):
            registry.library_of(bad)


def test_export_index_keeps_the_ids_of_one_distribution_and_stamps_it(fake_library, tmp_path):
    fake = registry.export_index(library="halvaro-fake")
    assert [r["id"] for r in fake] == ["halvaro.fake.mod.probe"], "halvaro.fakex. is not halvaro.fake."
    assert fake[0]["library"] == "halvaro-fake" and fake[0]["version"] == "9.9.9" and fake[0]["stage"] == "day1"
    cores = registry.export_index()
    assert cores and all(r["id"].startswith("halvaro.core.") and r["library"] == "halvaro-core" and r["version"] == core.__version__ for r in cores)
    assert not {"halvaro.fake.mod.probe", "halvaro.fakex.mod.other"} & {r["id"] for r in cores}, "the core index does not pick up another distribution"
    import yaml
    registry.export_index(tmp_path / "fake.yaml", library="halvaro-fake")
    doc = yaml.safe_load((tmp_path / "fake.yaml").read_text())
    assert [r["id"] for r in doc["functions"]] == ["halvaro.fake.mod.probe"] and doc["snapshot"] == core.snapshot_hash()
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(fake[0], registry.index_schema())


def test_export_index_refuses_a_bad_name_and_an_empty_distribution(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "halvaro.empty._version", types.SimpleNamespace(__version__="1.0.0"))
    for bad in ("halvaro_hr", "halvaro-HR", "hr", "halvaro-"):
        with pytest.raises(core.HalvaroError, match="not a distribution name"):
            registry.export_index(library=bad)
    with pytest.raises(core.HalvaroError, match="no registered function has the prefix halvaro.empty."):
        registry.export_index(library="halvaro-empty")
    with pytest.raises(core.HalvaroError, match="no version for halvaro-nothing"):
        registry.library_version("halvaro-nothing")


def test_installed_metadata_wins_over_the_source_tree_version(fake_library, monkeypatch):
    monkeypatch.setattr(registry.metadata, "version", lambda d: "7.7.7")
    assert registry.library_version("halvaro-fake") == "7.7.7" and registry.export_index(library="halvaro-fake")[0]["version"] == "7.7.7"
    assert core.make_envelope(1, "halvaro.fake.mod.probe").library_version == "7.7.7"


def test_a_version_module_without_a_version_raises(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "halvaro.bad._version", types.SimpleNamespace())
    with pytest.raises(core.HalvaroError, match="no version for halvaro-bad"):
        registry.library_version("halvaro-bad")


def test_make_envelope_stamps_the_version_of_the_distribution_of_the_function(fake_library):
    assert core.make_envelope(1, "halvaro.fake.mod.probe").library_version == "9.9.9" and core.make_envelope(1, "halvaro.fake.mod.probe").warnings == ()
    assert core.make_envelope(1, "halvaro.core.keys.parse_key").library_version == core.__version__
    assert core.make_envelope(1).library_version == core.__version__, "no function id: the core version"


def test_make_envelope_falls_back_to_the_core_version_with_a_warning_instead_of_failing():
    for fid in ("not_an_id", "halvaro.nothing.mod.f"):
        env = core.make_envelope(1, fid, warnings=("kept",))
        assert env.library_version == core.__version__ and env.warnings[0] == "kept" and "unknown" in env.warnings[1] and fid in env.warnings[1], fid
