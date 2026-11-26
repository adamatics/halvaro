"""Oracle of as_of_view (plan 5.4): hand worked restatement, then a plain python loop over the baseline lines for several booking periods."""
import pandas as pd

import halvaro.esg as esg
from halvaro.core import Context

M12 = Context(stage="month12", role="r")
LCOLS = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period", "supersedes_line_no", "prj_key", "quantity", "efac_key",
         "ref_type", "ref_key", "unit", "site_key", "subcategory"]


def _l(rows):
    full = [(le, per, sc, cat, no, None, "1", kg, sup, rf, sn, None, 1.0, "E", None, None, "l", None, None) for le, per, sc, cat, no, kg, sup, rf, sn in rows]
    return pd.DataFrame(full, columns=LCOLS).astype({"supersedes_line_no": "Int64"})


def _keys(frame):
    return sorted((r.le_key, r.period, int(r.scope), r.category, int(r.line_no)) for r in frame.itertuples())


def test_oracle_as_of_view_hand_worked_restatement():
    """route: hand reading of four lines. The original of 2025-03 is replaced by a restatement booked 2026-01; a line of 2026-02 exists from its own period."""
    L = _l([("LE-01", "2025-03", 1, "mobile_combustion", 1, 10.0, True, None, None),
            ("LE-01", "2025-03", 1, "mobile_combustion", 2, 12.0, False, "2026-01", 1),
            ("LE-01", "2026-02", 1, "mobile_combustion", 1, 7.0, False, None, None),
            ("LE-02", "2025-03", 2, "purchased_electricity", 1, 3.0, False, None, None)])
    at = lambda a: _keys(esg.as_of_view(L, a, context=M12))
    assert at("2025-02") == [], "no period is booked yet"
    assert at("2025-12") == [("LE-01", "2025-03", 1, "mobile_combustion", 1), ("LE-02", "2025-03", 2, "purchased_electricity", 1)], "as first booked: the original, not the restatement"
    assert at("2026-01") == [("LE-01", "2025-03", 1, "mobile_combustion", 2), ("LE-02", "2025-03", 2, "purchased_electricity", 1)], "the restatement replaces the original from its booking period on"
    assert at("2026-02") == [("LE-01", "2025-03", 1, "mobile_combustion", 2), ("LE-01", "2026-02", 1, "mobile_combustion", 1), ("LE-02", "2025-03", 2, "purchased_electricity", 1)]
    kg = lambda a: float(esg.as_of_view(L, a, context=M12)["kgco2e"].sum())
    assert kg("2025-12") == 13.0 and kg("2026-01") == 15.0 and kg("2026-02") == 22.0
    before = L.copy()
    esg.as_of_view(L, "2026-01", context=M12)
    pd.testing.assert_frame_equal(L, before)
