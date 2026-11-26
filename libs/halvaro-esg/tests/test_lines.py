"""Emission lines (plan 5.4): hand computed restatements, then the baseline release against the truth of the factor set update 2026-01 (6,964 lines restated, 2025)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _factors():
    cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to"]
    return pd.DataFrame([("EF-OLD", "fuel_diesel", "diesel", "DK", None, 2.0, "2025-01-01", "2025-12-31"), ("EF-NEW", "fuel_diesel", "diesel", "DK", None, 2.5, "2026-01-01", None),
                         ("EF-EL", "electricity_grid_average", "electricity", "DK", "location", 0.5, "2023-01-01", None)], columns=cols)


def _lines():
    """2025-03 diesel line 1 restated by line 2 (booked 2026-01); an unrestated 2025-04 line and a scope 2 line."""
    c = ["le_key", "period", "scope", "category", "line_no", "ref_type", "ref_key", "quantity", "efac_key", "kgco2e", "restated_from_period", "supersedes_line_no", "is_superseded", "method", "ghg_category"]
    rows = [("LE-01", "2025-03", 1, "mobile_combustion", 1, "MTR", "MTR-1", 100.0, "EF-OLD", 200.0, None, None, True, None, "1"),
            ("LE-01", "2025-03", 1, "mobile_combustion", 2, "MTR", "MTR-1", 100.0, "EF-NEW", 250.0, "2026-01", 1, False, None, "1"),
            ("LE-01", "2025-04", 1, "mobile_combustion", 1, "MTR", "MTR-1", 10.0, "EF-OLD", 20.0, None, None, False, None, "1"),
            ("LE-01", "2025-04", 2, "purchased_electricity", 1, "MTR", "MTR-2", 1000.0, "EF-EL", 500.0, None, None, False, "location", "2")]
    return pd.DataFrame(rows, columns=c).astype({"supersedes_line_no": "Int64"})


def test_the_two_bases_and_the_double_count_trap():
    L = _lines()
    assert esg.current_basis(L, context=M12).line_no.tolist() == [2, 1, 1] and esg.current_basis(L, context=M12).kgco2e.sum() == 770.0
    assert esg.as_first_booked(L, context=M12).kgco2e.sum() == 720.0 and len(esg.as_first_booked(L, context=M12)) == 3
    assert L.kgco2e.sum() == 970.0, "all lines added up counts the change twice"
    with pytest.raises(FrameError, match="1 original lines.*2025"):
        esg.assert_no_double_count(L, context=M12)
    assert esg.assert_no_double_count(esg.current_basis(L, context=M12), context=M12) is True and esg.assert_no_double_count(esg.as_first_booked(L, context=M12), context=M12) is True
    for bad, msg in ((L.assign(is_superseded=[True, None, False, False]), "is_superseded has nulls"), (pd.concat([L, L.iloc[:1]]), "more than one row"), (L.drop(columns="is_superseded"), "lacks column")):
        with pytest.raises(FrameError, match=msg):
            esg.current_basis(bad, context=M12)
    assert esg.current_basis(L.iloc[:0], context=M12).empty


def test_restatement_pairs_are_one_to_one_and_checked():
    p = esg.restatement_pairs(_lines(), context=M12)
    assert len(p) == 1 and p.iloc[0][["line_no_original", "line_no_restated", "efac_original", "efac_restated", "kg_original", "kg_restated", "delta_kg", "restated_from_period"]].tolist() == [1, 2, "EF-OLD", "EF-NEW", 200.0, 250.0, 50.0, "2026-01"]
    L = _lines()
    for bad, msg in ((L.assign(supersedes_line_no=pd.array([None, 7, None, None], dtype="Int64")), "no original"), (L.assign(quantity=[100.0, 99.0, 10.0, 1000.0]), "quantity or method"),
                     (L.assign(efac_key=["EF-OLD", "EF-OLD", "EF-OLD", "EF-EL"]), "same factor"), (L.assign(supersedes_line_no=pd.array([None, pd.NA, None, None], dtype="Int64")), "no supersedes_line_no")):
        with pytest.raises(FrameError, match=msg):
            esg.restatement_pairs(bad, context=M12)
    twice = pd.concat([L, L.iloc[[1]].assign(line_no=3)], ignore_index=True)
    with pytest.raises(FrameError, match="replaced by more than one"):
        esg.restatement_pairs(twice, context=M12)
    assert esg.restatement_pairs(L[L.restated_from_period.isna()], context=M12).empty


def test_as_of_view_uses_the_booking_periods_and_ignores_is_superseded():
    L = _lines()
    dec = esg.as_of_view(L, "2025-12", context=M12)
    assert sorted(zip(dec.period, dec.line_no)) == [("2025-03", 1), ("2025-04", 1), ("2025-04", 1)] and dec.kgco2e.sum() == 720.0, "as of 2025-12 the original stands and the restated line is not booked yet"
    jan = esg.as_of_view(L.assign(is_superseded=False), "2026-01", context=M12)
    assert jan.kgco2e.sum() == 770.0 and 1 not in jan[jan.period == "2025-03"].line_no.tolist(), "from 2026-01 the restated line replaces the original whatever is_superseded says"
    assert esg.as_of_view(L, "2025-03", context=M12).kgco2e.sum() == 200.0, "lines of later periods are not booked yet"
    for bad in ("2025-13", "2025", 2025, None):
        with pytest.raises(FrameError, match="period text"):
            esg.as_of_view(L, bad, context=M12)


def test_restatement_bridge_by_scope_category_and_family():
    b = esg.restatement_bridge(_lines(), _factors(), 2025, context=M12)
    assert b.iloc[0][["scope", "category", "family", "n_lines", "kg_first_booked", "kg_restated", "delta_kg", "delta_percent"]].tolist() == [1, "mobile_combustion", "fuel_diesel|diesel|DK|-", 1, 200.0, 250.0, 50.0, 25.0]
    assert esg.restatement_bridge(_lines(), _factors(), 2024, context=M12).empty
    f = _factors().assign(carrier=["diesel", "petrol", "electricity"])
    with pytest.raises(FrameError, match="factor family"):
        esg.restatement_bridge(_lines(), f, 2025, context=M12)
    with pytest.raises(FrameError, match="not in energy-esg.emission_factor"):
        esg.restatement_bridge(_lines(), _factors().iloc[1:], 2025, context=M12)
    for y in ("2025", 2025.0, True):
        with pytest.raises(FrameError, match="year"):
            esg.restatement_bridge(_lines(), _factors(), y, context=M12)


def test_validate_lines_rules():
    assert esg.validate_lines(_lines(), _factors(), context=M12).empty, "the restated line uses a factor that starts after its period: allowed because it is restated"
    r = lambda L: sorted(set(esg.validate_lines(L, _factors(), context=M12).rule))
    L = _lines()
    assert r(L.assign(kgco2e=[200.0, 250.0, 20.005, 500.0])) == ["value"] and r(L.assign(kgco2e=[200.0, 250.0, 20.0015, 500.0])) == []
    assert r(L.assign(efac_key=["EF-OLD", "EF-NEW", "EF-NEW", "EF-EL"])) == ["factor_validity", "value"] or r(L.assign(efac_key=["EF-OLD", "EF-NEW", "EF-NEW", "EF-EL"])) == ["factor_validity", "value"]
    assert r(L.assign(efac_key=["EF-OLD", "EF-NEW", "EF-X", "EF-EL"])) == ["unknown_factor"]
    assert r(L.assign(method=[None, None, None, None])) == ["method"] and r(L.assign(method=["market", None, None, "location"])) == ["method"]
    assert r(L.assign(ref_key=["MTR-1", "MTR-1", "PRJ-1", "MTR-2"])) == ["ref_prefix"] and r(L.assign(ref_type=["XXX"] + ["MTR"] * 3)) == ["ref_prefix"]
    assert r(L.assign(quantity=[np.nan, 100.0, 10.0, 1000.0])) == ["null_value"]
    dup = pd.concat([L, L.iloc[:1]])
    assert "duplicate_key" in r(dup)
    assert esg.validate_lines(L.iloc[:0], _factors(), context=M12).empty
    with pytest.raises(FrameError, match="more than one row for an efac_key"):
        esg.validate_lines(L, pd.concat([_factors(), _factors().iloc[:1]]), context=M12)


def test_review_cases_stale_flags_duplicates_dtypes_and_gaps_in_the_rules():
    L = _lines()
    with pytest.raises(FrameError, match="not flagged is_superseded"):
        esg.current_basis(L.assign(is_superseded=False), context=M12)
    twice = pd.concat([L, L.iloc[[1]].assign(line_no=3)], ignore_index=True)
    assert esg.as_of_view(twice, "2026-01", context=M12).kgco2e.sum() == 20.0 + 500.0 + 250.0 + 250.0, "two restated lines on one original: the original is gone once, no crash"
    only = L[["le_key", "period", "scope", "category", "line_no", "is_superseded", "restated_from_period", "supersedes_line_no"]]
    assert len(esg.as_of_view(only, "2025-12", context=M12)) == 3 and esg.assert_no_double_count(only[only.is_superseded == False].iloc[:0], context=M12), "the functions need only the columns of their sources"
    with pytest.raises(FrameError, match="more than one restated"):
        esg.restatement_pairs(twice, context=M12)
    mixed = L.assign(line_no=L.line_no.astype("Int64"), supersedes_line_no=L.supersedes_line_no.astype(float))
    assert len(esg.restatement_pairs(mixed, context=M12)) == 1 and esg.assert_no_double_count(esg.current_basis(mixed, context=M12), context=M12)
    with pytest.raises(FrameError, match="need a quantity"):
        esg.restatement_pairs(L.assign(quantity=[100.0, np.nan, 10.0, 1000.0]), context=M12)
    b = esg.restatement_bridge(pd.concat([L, L.iloc[[1]].assign(line_no=9, period="2024-03")]), _factors(), 2025, context=M12)
    assert len(b) == 1, "a broken pair in another year does not stop the bridge of this year"
    assert esg.restatement_bridge(L, _factors(), 2026, context=M12).empty
    with pytest.raises(FrameError, match="period text"):
        esg.as_of_view(L, "２０２５-12", context=M12)
    v = lambda x: sorted(set(esg.validate_lines(x, _factors(), context=M12).rule))
    assert v(L.assign(period=["2025-13", "2025-03", "2025-04", "2025-04"])) != [] and "period" in v(L.assign(period=["2025-13", "2025-03", "2025-04", "2025-04"]))
    assert v(L.assign(efac_key=["EF-OLD", "EF-OLD", "EF-OLD", "EF-EL"], kgco2e=[200.0, 200.0, 20.0, 500.0])) == ["restated_factor"], "a restated line on a factor that was valid anyway"
    assert v(L.assign(ghg_category=["1", "1", "1", "3.1"])) == ["category"] and v(L.assign(ghg_category=[None, "1", "1", "2"])) == ["category"]
    assert v(L.assign(supersedes_line_no=pd.array([None, None, None, None], dtype="Int64"))) == ["link"]
    assert v(L.assign(category=[None, "mobile_combustion", "mobile_combustion", "purchased_electricity"])) == ["null_value"]
    expired = _factors().assign(valid_to=["2025-03-31", None, None])
    r = esg.validate_lines(L, expired, context=M12)
    assert r.rule.tolist() == ["factor_validity"] and r.key.tolist() == ["LE-01 2025-04 1 mobile_combustion 1"], "valid_to is inclusive: March is inside, April is outside"


def test_unlinked_restated_lines_and_orphan_flags_are_refused():
    L = _lines()
    unlinked = L.assign(supersedes_line_no=pd.array([pd.NA] * 4, dtype="Int64"), is_superseded=[False, False, False, False])
    for call in (lambda: esg.current_basis(unlinked, context=M12), lambda: esg.assert_no_double_count(unlinked, context=M12), lambda: esg.as_of_view(unlinked, "2026-01", context=M12)):
        with pytest.raises(FrameError, match="no supersedes_line_no"):
            call()
    assert len(esg.as_of_view(unlinked, "2025-12", context=M12)) == 3, "a line restated after the as-of period does not matter to the view"
    ghost = L.assign(supersedes_line_no=pd.array([pd.NA, 99, pd.NA, pd.NA], dtype="Int64"))
    with pytest.raises(FrameError, match="not in the frame"):
        esg.current_basis(ghost, context=M12)
    lone = L.iloc[[0, 2, 3]]
    with pytest.raises(FrameError, match="no restated line replaces"):
        esg.current_basis(lone, context=M12)
    assert esg.assert_no_double_count(esg.current_basis(L, context=M12), context=M12) is True, "a filtered current basis passes: the replaced original is rightly absent"
