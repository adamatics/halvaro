"""Version of halvaro-hr from a Git tag (standard 1.4, issue #196, F6): configuration, tag form and CI job. The build itself is tried in the CI job halvaro-hr-package."""
import re
import tomllib
from pathlib import Path


LIB = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((LIB / "pyproject.toml").read_text(encoding="utf-8"))
VERSION_PY = LIB / "src" / "halvaro" / "hr" / "_version.py"


def test_the_version_is_dynamic_and_read_from_the_tag_by_setuptools_scm():
    assert "version" in PYPROJECT["project"]["dynamic"] and "version" not in PYPROJECT["project"]
    assert "version" not in PYPROJECT["tool"]["setuptools"].get("dynamic", {}), "no hand-edited version attribute"
    assert any(r.startswith("setuptools-scm==") for r in PYPROJECT["build-system"]["requires"]), "the build tool is pinned"
    scm = PYPROJECT["tool"]["setuptools_scm"]
    assert scm["root"] == "../.." and scm["version_file"] == "src/halvaro/hr/_version_scm.py" and scm["fallback_version"]
    assert "halvaro-hr/v*" in scm["git_describe_command"], "only tags of this library count"


def test_the_tag_form_is_halvaro_hr_v_major_minor_patch():
    rx = re.compile(PYPROJECT["tool"]["setuptools_scm"]["tag_regex"])
    assert rx.match("halvaro-hr/v0.2.1")["version"] == "0.2.1" and rx.match("halvaro-hr/v10.0.12")["version"] == "10.0.12"
    for other in ("baseline-2026-10-13", "halvaro-core/v0.1.0", "halvaro-hr/v1.2", "v1.2.3", "halvaro-hr/v1.2.3-rc1", "halvaro-hr/1.2.3"):
        assert not rx.match(other), other


def test_the_committed_version_file_is_the_fallback_and_never_a_built_file():
    text = VERSION_PY.read_text(encoding="utf-8")
    assert "from ._version_scm import __version__" in text and re.search(r'^\s+__version__ = "\d+\.\d+\.\d+"', text, re.M), "import the build output, keep the fallback"
    assert "commit_id" not in text and "version_tuple" not in text, "a version file written by the build was committed"
    namespace: dict = {}
    exec(compile(text, str(VERSION_PY), "exec"), {"__package__": "halvaro.hr"}, namespace)
    assert re.fullmatch(r"\d+\.\d+\.\d+", namespace["__version__"]) or (LIB / "src" / "halvaro" / "hr" / "_version_scm.py").exists()
