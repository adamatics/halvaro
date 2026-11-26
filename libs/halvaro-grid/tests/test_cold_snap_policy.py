"""D12, owner decision of 2026-11-13: `cold_snaps` reads the number of core days from the proposed fact policy.grid.cold_snap_min_core_days (2) when `min_core_days` is not given. On the baseline weather 2 and 3 give the same snaps."""
import pandas as pd

import halvaro.grid as grid
from halvaro.core import Context, fact, registry

from test_capacity import _daily

M12 = Context(stage="month12", role="r")


def test_the_fact_is_proposed_two_and_the_function_declares_it():
    f = fact("policy.grid.cold_snap_min_core_days")
    assert f.value == 2 and f.status in ("proposed", "verified")      # lane F3 (issue #543), approved edit: lane F2 accepted the fact (status verified)
    assert "policy.grid.cold_snap_min_core_days" in registry.registered()["halvaro.grid.capacity.cold_snaps"].facts


def test_the_default_reads_the_fact_and_an_explicit_number_overrides_it():
    two = _daily([-9.0, -9.0, -1.0, -9.0, -9.0, -1.0])
    assert len(grid.cold_snaps(two, context=M12)) == 2, "two core days are a snap by the fact"
    assert grid.cold_snaps(two, min_core_days=3, context=M12).empty, "the old default stays available by name"
    pd.testing.assert_frame_equal(grid.cold_snaps(two, context=M12), grid.cold_snaps(two, min_core_days=2, context=M12))
    three = _daily([-9.0, -9.0, -9.0, -1.0])
    pd.testing.assert_frame_equal(grid.cold_snaps(three, context=M12), grid.cold_snaps(three, min_core_days=3, context=M12))
