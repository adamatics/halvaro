"""D12 (known-defects.md): the library defaults against the proposed facts policy.grid.cold_snap and policy.grid.min_peak_completeness (proposed; cold_snap is text, the completeness share is a number).

The numbers are read out of the fact text, never typed. What matches passes; what does not is a strict xfail with the measured numbers. The min_core_days difference is closed (the default reads the fact); the missing-run rule of peak_load is still open.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, fact

from test_capacity import _meas, _sensor, _weather

M12 = Context(stage="month12", role="r")
COLD = str(fact("policy.grid.cold_snap").value)
PEAK = float(fact("policy.grid.min_peak_completeness").value)


def _default(fn, name):
    return inspect.signature(fn).parameters[name].default


def test_the_facts_are_proposed_text_with_the_numbers_the_library_defaults_are_compared_with():
    assert fact("policy.grid.cold_snap").status in ("proposed", "verified") and fact("policy.grid.min_peak_completeness").status in ("proposed", "verified")      # lane F3 (issue #543), approved edit: lane F2 accepted the facts (status verified)
    assert re.search(r"at least (\d+) consecutive days", COLD) and re.search(r"minus (\d+) degrees", COLD)


def test_cold_snap_core_threshold_default_equals_the_fact():
    assert _default(grid.cold_snaps, "core_c") == -float(re.search(r"minus (\d+) degrees", COLD).group(1))


def test_peak_completeness_default_equals_the_fact():
    assert _default(grid.peak_load, "min_completeness") == pytest.approx(PEAK)


def test_cold_snap_minimum_core_days_default_equals_the_fact():
    """D12 closed (owner decision of 2026-11-13): the default is None, which reads the numeric fact, and that fact equals the number in the text of policy.grid.cold_snap."""
    n = int(re.search(r"at least (\d+) consecutive days", COLD).group(1))
    assert fact("policy.grid.cold_snap_min_core_days").value == n and _default(grid.cold_snaps, "min_core_days") is None


@pytest.mark.xfail(strict=True, reason="D12: the note of the proposed fact policy.grid.min_peak_completeness says a peak is also invalid when a missing run lies within 2 hours of it (returned with valid false and the reason); peak_load only tests the share of ok samples (here 38 of 40 = 0.95, valid true) and has no reason column")
def test_peak_with_a_missing_run_next_to_it_is_not_valid():
    n = 40
    values = [60.0 + (i % 5) for i in range(n)]
    values[20] = 130.0
    flags = ["ok"] * n
    for i in (21, 22):
        flags[i], values[i] = "missing", np.nan
    series = pd.concat([_meas("R-LOAD", values, flags)])
    z = grid.zone_load_percent(series, _sensor(), context=M12)
    p = grid.peak_load(z, _sensor(), _weather(), context=M12).set_index("sns_key").loc["R-LOAD"]
    assert p.completeness >= 0.9 and p.peak_percent == 130.0
    assert p.valid is False or not p.valid
