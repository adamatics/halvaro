"""An app that calls a staged function the only correct way, with context=, passes mypy, and mypy reads the result type from the package (lane P3, second and third round, #457).

The decorator types a staged function as Callable[..., R] for a caller: context= is accepted and the result type is kept, but the arguments are not checked (item 13 of #440).
The test fails when the decorator hides context again, and when mypy does not read the package at all (then the revealed result type is Any)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1]
APP = '''
import pandas as pd
from halvaro.core import Context
from halvaro.grid import zone_design_capacity

ctx = Context(stage="month12", role="app")
reveal_type(zone_design_capacity)
result = zone_design_capacity(pd.DataFrame(), context=ctx)
'''


def test_a_call_with_context_type_checks_for_a_caller(tmp_path):
    pytest.importorskip("mypy")
    app = tmp_path / "app.py"
    app.write_text(APP, encoding="utf-8")
    paths = ":".join(str(p) for p in (LIB / "src", LIB.parent / "halvaro-core" / "src"))
    r = subprocess.run([sys.executable, "-m", "mypy", "--no-incremental", "--cache-dir", str(tmp_path / "cache"), "--follow-imports=silent", str(app)],
                       capture_output=True, text=True, env={"MYPYPATH": paths, "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "-> pandas.core.frame.DataFrame" in r.stdout, "mypy did not read the result type from the package: " + r.stdout
