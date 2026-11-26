"""Emission factors (plan 5.1): hand computed synthetic frames."""
import numpy as np
import pandas as pd
import pytest

import halvaro.esg as esg
from halvaro.core import Context, FrameError

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")
NOTE = "VERIFY: synthetic value, not for real reporting"


def _f(rows):
    cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set", "synthetic", "verify_note"]
    return pd.DataFrame([(f"EFAC-{i:04d}", *r, True, NOTE) for i, r in enumerate(rows, 1)], columns=cols)


ROWS = [("fuel_diesel", "diesel", "DK", None, 2.62, "2023-01-01", "2023-12-31", "FS-2023"), ("fuel_diesel", "diesel", "DK", None, 2.60, "2024-01-01", "2025-12-31", "FS-2023-25"),
        ("fuel_diesel", "diesel", "DK", None, 2.63, "2026-01-01", None, "FS-2026"), ("electricity_grid_average", "electricity", "DK", "location", 0.10, "2023-01-01", None, "FS-2023-25"),
        ("electricity_grid_average", "electricity", "DK", "market", 0.20, "2023-01-01", None, "FS-2023-25")]


def test_family_key_joins_the_four_parts_and_marks_null_parts():
    k = esg.family_key(_f(ROWS), context=M12)
    assert k.tolist() == ["fuel_diesel|diesel|DK|-"] * 3 + ["electricity_grid_average|electricity|DK|location", "electricity_grid_average|electricity|DK|market"]
    assert k.index.equals(_f(ROWS).index) and k.name == "family_key"
    assert esg.family_key(_f(ROWS).iloc[:0], context=M12).empty
    with pytest.raises(FrameError, match="lacks column"):
        esg.family_key(_f(ROWS).drop(columns="region"), context=M12)


def test_factor_on_valid_to_is_inclusive_and_null_is_open():
    f = _f(ROWS)
    on = lambda d, **kw: esg.factor_on(f, "fuel_diesel", "DK", d, carrier="diesel", context=M12, **kw)
    assert on("2023-12-31").value.kgco2e_per_unit.tolist() == [2.62], "valid_to is inclusive"
    assert on("2024-01-01").value.kgco2e_per_unit.tolist() == [2.60] and on("2025-12-31").value.efac_key.tolist() == ["EFAC-0002"]
    assert on("2026-01-01").value.kgco2e_per_unit.tolist() == [2.63] and on("2040-05-05").value.kgco2e_per_unit.tolist() == [2.63], "a null valid_to is current"
    assert on("2024-07").value.efac_key.tolist() == ["EFAC-0002"], "a period is its first day"
    assert on(pd.Timestamp("2026-01-01")).as_of.isoformat() == "2026-01-01"
    with pytest.raises(FrameError, match="no factor"):
        on("2022-12-31")
    with pytest.raises(FrameError, match="no factor"):
        esg.factor_on(f, "fuel_diesel", "DE", "2024-01-01", carrier="diesel", context=M12)
    for bad in (2024, True, "not a date", pd.Timestamp("2024-01-01", tz="UTC")):
        with pytest.raises(FrameError, match="date"):
            on(bad)
    e = esg.factor_on(f, "electricity_grid_average", "DK", "2024-01-01", carrier="electricity", method="market", context=M12)
    assert e.value.kgco2e_per_unit.tolist() == [0.20] and e.factor_sets == ("FS-2023-25",)
    with pytest.raises(FrameError, match="no factor"):
        esg.factor_on(f, "electricity_grid_average", "DK", "2024-01-01", carrier="electricity", context=M12)           # method None matches a null method only
    overlap = pd.concat([f, f.iloc[[1]].assign(efac_key="EFAC-9999")])
    with pytest.raises(FrameError, match="2 factors.*EFAC-0002, EFAC-9999"):
        esg.factor_on(overlap, "fuel_diesel", "DK", "2024-06-01", carrier="diesel", context=M12)


def test_factor_results_are_synthetic_and_verify_never_ok():
    f = _f(ROWS)
    r = esg.factor_on(f, "fuel_diesel", "DK", "2024-06-01", carrier="diesel", context=M12)
    assert isinstance(r, esg.Provenance) and r.status == "VERIFY+synthetic" and r.synthetic is True and r.verify_facts == (NOTE,) and r.function == "halvaro.esg.factors.factor_on"
    flag = esg.flag_synthetic(f, context=M12)
    assert flag.status == "VERIFY+synthetic" and flag.warnings == () and flag.value.columns.tolist() == ["efac_key", "synthetic", "verify_note"] and len(flag.value) == 5
    odd = f.assign(synthetic=[True, False, True, True, True], verify_note=[NOTE, NOTE, None, NOTE, NOTE])
    w = esg.flag_synthetic(odd, context=M12)
    assert w.synthetic is False and len(w.warnings) == 2 and "not flagged synthetic" in w.warnings[0] and "no VERIFY note" in w.warnings[1]
    assert w.status == "VERIFY", "a result with a non synthetic row is not synthetic, but the VERIFY note stays"


def test_factor_set_diff_percent_change_sides_and_multi_set_basis():
    f = _f(ROWS + [("fuel_petrol", "petrol", "DK", None, 0.0, "2026-01-01", None, "FS-2026"), ("fuel_petrol", "petrol", "DK", None, 2.0, "2025-01-01", "2025-12-31", "FS-2025"),
                   ("waste_wood", None, "EU", None, 1.0, "2026-01-01", None, "FS-2026")])
    d = esg.factor_set_diff(f, ["FS-2023-25", "FS-2025"], "FS-2026", context=M12).value.set_index("family")
    assert d.loc["fuel_diesel|diesel|DK|-", ["old_value", "new_value", "change_percent", "side"]].tolist() == [2.60, 2.63, 1.15, "both"]
    assert d.loc["electricity_grid_average|electricity|DK|market", "side"] == "old_only" and np.isnan(d.loc["electricity_grid_average|electricity|DK|market", "change_percent"])
    assert d.loc["waste_wood|-|EU|-", "side"] == "new_only"
    p = d.loc["fuel_petrol|petrol|DK|-"]
    assert p.old_value == 2.0 and p.new_value == 0.0 and p.change_percent == -100.0
    z = esg.factor_set_diff(f.assign(kgco2e_per_unit=[2.62, 2.60, 2.63, 0.1, 0.2, 0.0, 0.0, 1.0]), "FS-2025", "FS-2026", context=M12).value.set_index("family")
    assert np.isnan(z.loc["fuel_petrol|petrol|DK|-", "change_percent"]), "no percent from a zero old value"
    assert esg.factor_set_diff(f, "FS-2025", "FS-2026", context=M12).factor_sets == ("FS-2025", "FS-2026")
    for old, msg in (("FS-9999", "not in the table"), ([], "factor set name"), (["FS-2023", "FS-2023-25"], "more than one row"), (5, "factor set name")):
        with pytest.raises(FrameError, match=msg):
            esg.factor_set_diff(f, old, "FS-2026", context=M12)


def test_review_cases_duplicate_index_status_never_ok_nullable_floats_and_mid_month_boundaries():
    a, b = _f(ROWS[:1]), _f([("fuel_petrol", "petrol", "DK", None, 2.3, "2023-01-01", None, "FS-B")])
    dup = pd.concat([a, b])                                                           # both rows carry the label 0
    r = esg.factor_on(dup, "fuel_petrol", "DK", "2024-06-01", carrier="petrol", context=M12)
    assert r.value.efac_key.tolist() == ["EFAC-0001"] and r.value.kgco2e_per_unit.tolist() == [2.3] and r.factor_sets == ("FS-B",), "selected by position, not by index label"
    plain = _f(ROWS[:2]).assign(synthetic=False, verify_note=None)
    for env in (esg.factor_on(plain, "fuel_diesel", "DK", "2023-06-01", carrier="diesel", context=M12), esg.flag_synthetic(plain, context=M12)):
        assert env.status == "VERIFY" and env.synthetic is False, "not synthetic and not noted is still not ok"
    mixed = esg.flag_synthetic(_f(ROWS[:2]).assign(verify_note=[NOTE, None]), context=M12)
    assert mixed.status == "synthetic" and "no VERIFY note" in mixed.warnings[0]
    assert esg.flag_synthetic(_f(ROWS[:2]).assign(verify_note=[NOTE, "fine"]), context=M12).status == "synthetic", "a note without the VERIFY token is no note"
    odd = esg.flag_synthetic(_f(ROWS[:3]).assign(synthetic=pd.array([True, None, False], dtype="boolean")), context=M12)
    assert odd.status == "VERIFY" and "2 factor rows are not flagged synthetic" in odd.warnings[0]
    nullable = _f(ROWS[:1] + [("waste_wood", None, "EU", None, 1.0, "2026-01-01", None, "FS-2026")]).assign(kgco2e_per_unit=pd.array([2.0, 1.0], dtype="Float64"))
    d = esg.factor_set_diff(nullable, "FS-2023", "FS-2026", context=M12).value.set_index("family")
    assert d.loc["fuel_diesel|diesel|DK|-", "old_value"] == 2.0 and np.isnan(d.loc["fuel_diesel|diesel|DK|-", "change_percent"]) and d.loc["waste_wood|-|EU|-", "side"] == "new_only"
    mid = _f([("fuel_diesel", "diesel", "DK", None, 1.0, "2024-01-01", "2024-06-15", "FS-A"), ("fuel_diesel", "diesel", "DK", None, 2.0, "2024-06-16", None, "FS-B")])
    at = lambda on: esg.factor_on(mid, "fuel_diesel", "DK", on, carrier="diesel", context=M12).value.kgco2e_per_unit.iloc[0]
    assert (at("2024-06-15"), at("2024-06-16"), at("2024-06")) == (1.0, 2.0, 1.0), "a period is its first day, a mid month boundary is exact"
    two = _f([("fuel_diesel", "diesel", "DK", None, 1.0, "2024-01-01", None, "FS-A"), ("fuel_diesel", "hvo", "DK", None, 9.0, "2024-01-01", None, "FS-A")])
    assert esg.factor_on(two, "fuel_diesel", "DK", "2024-02-01", carrier="hvo", context=M12).value.kgco2e_per_unit.tolist() == [9.0], "the carrier is part of the family"
    zero = esg.factor_set_diff(_f([("fuel_diesel", "diesel", "DK", None, 0.0, "2024-01-01", None, "FS-A"), ("fuel_diesel", "diesel", "DK", None, 5.0, "2025-01-01", None, "FS-B")]), "FS-A", "FS-B", context=M12).value
    assert np.isnan(zero.change_percent.iloc[0]), "a percent from zero is null, never inf"
    mixed_tz = _f(ROWS[:1]).assign(valid_to=["2024-12-31T00:00:00+01:00"]).pipe(lambda x: pd.concat([x, x.assign(valid_to="2024-12-31T00:00:00+02:00", efac_key="EF2")]))
    with pytest.raises(FrameError):
        esg.factor_on(mixed_tz, "fuel_diesel", "DK", "2024-01-01", carrier="diesel", context=M12)


def test_product_basis_share_is_the_table_value():
    rows = _f([("purchased_goods_product_footprint", None, "ALL", None, 0.3339, "2023-01-01", None, "FS-CONST")] + ROWS)
    assert esg.product_basis_share(rows, context=M12) == 0.3339
    for bad in (rows.iloc[1:], pd.concat([rows, rows.iloc[:1]]), rows.assign(kgco2e_per_unit=[1.5] + [1.0] * 5)):
        with pytest.raises(FrameError):
            esg.product_basis_share(bad, context=M12)
