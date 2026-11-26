"""Boundary cases that the oracles of lane L2 left open (lane P1, third round of P1.5): a mutation that refuses days=1 of on_call and one that refuses the install year 2200 of element_age were not caught. No release needed."""
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import FrameError

from test_oracle_callouts import M12, _got, _rota
from test_oracle_geometry import _ge


def test_on_call_oracle_a_window_of_one_day_covers_the_start_day_only():
    """halvaro.grid.callouts.on_call: with days=1 a rota row covers its start day and not the day after (by hand: row 5 January, days 1: on call on 5 January, nobody on 6 January); days=0 and days=True are refused."""
    rota = _rota([("A", "2026-01-05", "a1", "b1")])
    assert _got(grid.on_call(rota, "2026-01-05", days=1, context=M12)) == [("A", pd.Timestamp("2026-01-05").date(), "a1", "b1")]
    assert _got(grid.on_call(rota, "2026-01-06", days=1, context=M12)) == []
    assert len(grid.on_call(rota, "2026-01-11", days=7, context=M12)) == 1 and grid.on_call(rota, "2026-01-12", days=7, context=M12).empty
    for bad in (0, True, 1.5):
        with pytest.raises(FrameError, match="days"):
            grid.on_call(rota, "2026-01-05", days=bad, context=M12)


def test_element_age_oracle_install_years_1800_and_2200_are_valid_1799_and_2201_are_refused():
    """halvaro.grid.geometry.element_age: the install years 1800 and 2200 are inside "1800 to 2200" and count from 1 January of the year (by hand: 2200-01-01 to 2201-01-01 is 365 days, as 2200 is no leap year: 365 / 365.25 = 0.9993, shown as 1.0;
    1800-01-01 to 1801-01-01 is 365 days, 1.0); 1799, 2201 and 1800.5 raise FrameError naming the range."""
    assert grid.element_age(_ge([(2200, "in_service", None)]), "2201-01-01", context=M12).iloc[0] == 1.0
    assert grid.element_age(_ge([(1800, "in_service", None)]), "1801-01-01", context=M12).iloc[0] == 1.0
    for bad in (1799, 2201, 1800.5):
        with pytest.raises(FrameError, match="1800 to 2200"):
            grid.element_age(_ge([(bad, "in_service", None)]), "2026-01-01", context=M12)
