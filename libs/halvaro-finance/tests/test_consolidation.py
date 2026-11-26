"""Consolidation (plan 5.8): hand computed entries, matches, movements and translation, then the baseline release against finance-reporting."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal, registry

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _ce(rows):
    cols = ["fiscal_year", "period", "entry_no", "entry_type", "basis", "debit_le_key", "debit_gl_key", "credit_le_key", "credit_gl_key", "amount_dkk", "difference_dkk"]
    return pd.DataFrame(rows, columns=cols)


def _entries():
    return _ce([(2025, "2025-01", 1, "investment", "opening_balance", "LE-02", "GL-3000", "LE-01", "GL-1500", 100.0, 0.0), (2025, "2025-01", 2, "ic_loan", "opening_balance", "LE-02", "GL-4120", "LE-01", "GL-1510", 50.0, 0.0),
                (2025, "2025-01", 3, "ic_trade_revenue", "period_movement", "LE-01", "GL-5400", "LE-02", "GL-8350", 20.0, 0.0), (2025, "2025-01", 4, "ic_balance", "period_movement", "LE-02", "GL-4800", "LE-01", "GL-2300", 5.0, 0.0)])


def test_eliminations_structure_balance_types_and_period_sums():
    ok = fin.eliminations(_entries(), context=M12)
    assert ok.empty
    bad = _entries().assign(amount_dkk=[100.0, -1.0, 20.0, 5.0], difference_dkk=[0.0, 0.0, 0.02, 0.0], credit_gl_key=["GL-1500", "GL-1510", "GL-5400", "GL-2300"], credit_le_key=["LE-01", "LE-01", "LE-01", "LE-01"])
    bad.loc[2, "debit_le_key"] = "LE-01"
    r = fin.eliminations(bad, context=M12)
    assert {"non_positive_amount", "entry_unbalanced", "same_account"} <= set(r.rule) and "#2" in r.key[r.rule == "non_positive_amount"].iloc[0]
    assert fin.eliminations(_entries().iloc[:2], context=M12).rule.tolist() == ["entry_type_missing"] and fin.eliminations(_entries().iloc[:2], required_types=("investment",), context=M12).empty
    g = pd.DataFrame({"period": ["2025-01", "2025-01", "2025-02"], "gl_key": ["GL-1", "GL-2", "GL-1"], "elimination_dkk": [3.0, -2.4, 0.0]})
    assert fin.eliminations(_entries(), g, context=M12).rule.tolist() == ["period_not_zero"]
    assert fin.eliminations(_entries(), g, period_tolerance=1.0, context=M12).empty
    with pytest.raises(FrameError, match="more than one row"):
        fin.eliminations(pd.concat([_entries(), _entries().iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="tolerance"):
        fin.eliminations(_entries(), tolerance=-1, context=M12)


def test_intercompany_match_recomputes_difference_status_and_fx():
    m = pd.DataFrame({"ic_ref": ["IC/1", "IC/2", "IC/3"], "kind": "management_fee", "period": "2025-01", "amount_le01_dkk": [74600.0, 100.0, 50.0], "amount_le02_dkk": [74600.0, 101.5, 50.0],
                      "amount_le02_eur": [10000.0, 13.6, 7.0], "difference_dkk": [0.0, -1.5, 0.0], "status": ["matched", "difference", "matched"]})
    r = fin.intercompany_match(m, context=M12)
    v = r.value.set_index("ic_ref")
    assert r.status == "ok" and v.loc["IC/1", "status"] == "matched" and v.loc["IC/2", "status"] == "difference" and v.loc["IC/2", "difference_dkk"] == -1.5
    assert v.agrees.tolist() == [True, True, True], "the stored status and difference agree with the recomputation for all three"
    assert bool(v.loc["IC/1", "fx_ok"]) and not bool(v.loc["IC/3", "fx_ok"]), "7 EUR at 7.46 is 52.22, not 50"
    assert fin.intercompany_match(m, tolerance_dkk=2.0, context=M12).value.set_index("ic_ref").loc["IC/2", "status"] == "matched"
    with pytest.raises(FrameError, match="one row per ic_ref"):
        fin.intercompany_match(pd.concat([m, m.iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="eur_rate"):
        fin.intercompany_match(m, eur_rate=0, context=M12)


def test_group_trial_balance_adds_entities_adjustments_and_movement_eliminations():
    jl = pd.DataFrame({"le_key": ["LE-01", "LE-01", "LE-02", "LE-02", "LE-01"], "period": "2025-01", "gl_key": ["GL-5400", "GL-2300", "GL-8350", "GL-4800", "GL-1000"],
                       "amount_dkk": [-20.0, 5.0, 20.0, -5.0, 999.0], "source": ["ar", "ar", "ar", "ar", "opening"]})
    ra = pd.DataFrame({"period": ["2025-01"], "gl_key": ["GL-9400"], "debit_dkk": [7.0], "credit_dkk": [0.0]})
    ce = _entries()
    ce.loc[2, ["debit_gl_key", "credit_gl_key", "debit_le_key", "credit_le_key"]] = ["GL-5400", "GL-8350", "LE-02", "LE-01"]
    r = fin.group_trial_balance(jl, ra, _entries(), context=M12)
    v = r.value.set_index("gl_key")
    assert v.loc["GL-5400", ["le01_movement_dkk", "elimination_dkk", "movement_dkk"]].tolist() == [-20.0, 20.0, 0.0], "the revenue of LE-01 is eliminated"
    assert v.loc["GL-8350", ["le02_movement_dkk", "elimination_dkk", "movement_dkk"]].tolist() == [20.0, -20.0, 0.0] and v.loc["GL-9400", "adjustment_dkk"] == 7.0
    assert "GL-1000" not in v.index and "GL-1500" not in v.index, "opening journals are not movement, opening-basis entries are not a movement elimination"
    assert abs(r.value.movement_dkk.sum() - 7.0) < 1e-9 and r.status == "ok"
    with pytest.raises(FrameError, match="beyond LE-01 and LE-02"):
        fin.group_trial_balance(jl.assign(le_key="LE-09"), ra, _entries(), context=M12)
    with pytest.raises(FrameError, match="null amount_dkk"):
        fin.group_trial_balance(jl.assign(amount_dkk=jl.amount_dkk.where(jl.index != 0, np.nan)), ra, _entries(), context=M12)


def test_translation_check_reports_rounding_and_refuses_a_rate_that_is_not_fixed():
    tb = pd.DataFrame({"le_key": "LE-02", "period": "2025-12", "gl_key": ["GL-1", "GL-2", "GL-3"], "currency": "EUR", "closing_balance": [1000.005, -999.99, 5.0], "closing_balance_dkk": [7460.04, -7459.92, 37.30]})
    r = fin.translation_check(tb, context=M12)
    v = r.value.iloc[0]
    assert r.status == "ok" and v.n_lines == 3 and v.sum_dkk == 37.42 and abs(v.rounding_dkk) < 0.1 and v.max_line_rounding_dkk < 0.1
    assert fin.translation_check(tb.assign(period="2025-06"), context=M12).value.empty and not fin.translation_check(tb.assign(period="2025-06"), month=6, context=M12).value.empty
    with pytest.raises(FrameError, match="not the fixed rate"):
        fin.translation_check(tb, eur_rate=7.5, context=M12)
    with pytest.raises(FrameError, match="month"):
        fin.translation_check(tb, month=13, context=M12)


def test_stage_registry_and_facade_for_consolidation():
    reg = registry.registered()
    for n in ("eliminations", "intercompany_match", "group_trial_balance", "translation_check"):
        assert f"halvaro.finance.consolidation.{n}" in reg and n in fin.__all__
    with pytest.raises(StageRefusal):
        fin.eliminations(pd.DataFrame(), context=M3)
