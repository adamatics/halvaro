"""Project view: hand computed synthetic cases for the rules and boundaries."""

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

CTX = Context(stage="month3", role="r")
CAP = 0.995


def _pf(rows):
    """rows: (prj_key, period, contract_value, eac, actual_cost, billed)."""
    cols = ["prj_key", "period", "contract_value", "eac", "actual_cost", "billed"]
    f = pd.DataFrame(rows, columns=cols)
    f["currency"], f["committed_cost"] = "EUR", 10.0
    return f


def test_running_project_is_cost_over_eac_and_capped_before_completion():
    f = _pf([("P1", "2025-03", 1000.0, 800.0, 400.0, 0.0), ("P1", "2025-04", 1000.0, 800.0, 799.0, 0.0), ("P1", "2025-05", 1000.0, 800.0, 800.0, 0.0)])
    pc = fin.percent_complete(f, {}, cap=CAP, context=CTX)
    assert pc.tolist() == [50.0, 99.5, 99.5] and pc.name == "percent_complete" and pc.index.equals(f.index)
    assert fin.revenue_recognised(f, {}, cap=CAP, context=CTX).tolist() == [500.0, 995.0, 995.0]
    assert fin.percent_complete(f, {}, cap=1.0, context=CTX).tolist() == [50.0, 99.88, 100.0], "99.875 percent rounds to 99.88; the cap is a parameter"


def test_completion_on_the_last_day_of_the_period_and_a_day_later():
    f = _pf([("P1", "2025-05", 1000.0, 800.0, 400.0, 0.0)])
    assert fin.percent_complete(f, {"P1": "2025-05-31"}, cap=CAP, context=CTX).tolist() == [100.0], "ended on the last day: complete in that period"
    assert fin.percent_complete(f, {"P1": "2025-06-01"}, cap=CAP, context=CTX).tolist() == [50.0]
    assert fin.revenue_recognised(f, {"P1": "2025-05-01"}, cap=CAP, context=CTX).tolist() == [1000.0]
    cases = [(pd.Series({"P1": pd.Timestamp("2025-05-31")}), [100.0]), (pd.DataFrame({"prj_key": ["P1", "P2"], "actual_end": [pd.Timestamp("2025-05-31"), None]}), [100.0]), ({"P1": None}, [50.0])]
    for src, want in cases:
        assert fin.percent_complete(f, src, cap=CAP, context=CTX).tolist() == want, type(src)


def test_loss_provision_is_the_unrecognised_share_of_the_expected_loss():
    f = _pf([("P1", "2025-03", 1000.0, 1200.0, 600.0, 0.0), ("P1", "2025-04", 1000.0, 1200.0, 900.0, 0.0), ("P2", "2025-04", 1000.0, 900.0, 450.0, 0.0)])
    assert fin.loss_provision(f, {}, cap=CAP, context=CTX).tolist() == [100.0, 50.0, 0.0]
    assert fin.loss_provision(f, {"P1": "2025-04-30"}, cap=CAP, context=CTX).tolist() == [100.0, 0.0, 0.0], "none once the project has ended"


def test_contract_position_splits_asset_and_liability():
    f = _pf([("P1", "2025-03", 1000.0, 800.0, 400.0, 300.0), ("P1", "2025-04", 1000.0, 800.0, 400.0, 700.0), ("P1", "2025-05", 1000.0, 800.0, 400.0, 500.0)])
    c = fin.contract_position(f, {}, cap=CAP, context=CTX)
    assert c.contract_position.tolist() == [200.0, -200.0, 0.0] and c.wip.tolist() == [200.0, 0.0, 0.0] and c.contract_liability.tolist() == [0.0, 200.0, 0.0]
    assert list(c.columns) == ["prj_key", "period", "revenue_recognised", "billed", "contract_position", "wip", "contract_liability"]


def test_the_fraction_refuses_a_bad_cap_and_an_empty_eac():
    f = _pf([("P1", "2025-03", 1000.0, 800.0, 400.0, 0.0)])
    for bad in (0, 1.5, -0.1, None, True, "0.995"):
        with pytest.raises(FrameError, match="cap must be a number"):
            fin.percent_complete(f, {}, cap=bad, context=CTX)
    with pytest.raises(FrameError, match="EAC of zero or null"):
        fin.percent_complete(f.assign(eac=0.0), {}, cap=CAP, context=CTX)
    assert fin.percent_complete(f.assign(eac=0.0), {"P1": "2025-03-31"}, cap=CAP, context=CTX).tolist() == [100.0]
    with pytest.raises(TypeError):
        fin.percent_complete(f, {}, context=CTX)


def _full(rows):
    f = _pf([(r[0], r[1], r[2], r[3], r[4], 0.0) for r in rows])
    f["revenue_recognised"] = [r[5] for r in rows]
    f["loss_provision"] = [r[6] for r in rows]
    return f


def test_project_margin_has_two_named_margins():
    f = _full([("P1", "2025-03", 1000.0, 800.0, 200.0, 250.0, 0.0), ("P1", "2025-04", 1000.0, 1200.0, 600.0, 500.0, 100.0), ("P1", "2025-05", 1000.0, 800.0, 0.0, 0.0, 0.0)])
    m = fin.project_margin(f, context=CTX)
    assert list(m.columns) == ["prj_key", "period", "margin_pct", "forecast_margin_pct"]
    assert m.margin_pct.iloc[:2].tolist() == [20.0, -40.0] and m.forecast_margin_pct.tolist() == [20.0, -20.0, 20.0]
    assert np.isnan(m.margin_pct.iloc[2]), "no revenue yet: no margin to date"
    assert fin.project_margin(f.assign(contract_value=0.0), context=CTX).forecast_margin_pct.isna().all()


def _manual():
    return pd.DataFrame({"le_key": "LE-02", "journal_no": [7, 7, 9], "posting_date": pd.to_datetime(["2025-12-18", "2025-12-18", "2026-02-10"]), "description": ["wd", "wd", "other"],
                         "gl_key": ["GL-5190", "GL-2100", "GL-5190"], "prj_key": ["P1", "P1", "P2"], "currency": "EUR", "amount": [100.0, -100.0, 5.0], "amount_dkk": [746.0, -746.0, 37.3]})


def test_write_down_journal_selects_the_project_and_account_only():
    w = fin.write_down_journal(_manual(), "P1", context=CTX)
    assert w.journal_no.tolist() == [7] and w.amount.tolist() == [100.0] and w.amount_dkk.tolist() == [746.0] and list(w.columns) == ["le_key", "journal_no", "posting_date", "description", "currency", "amount", "amount_dkk"]
    assert fin.write_down_journal(_manual(), "P3", context=CTX).empty, "an empty frame, never a guess"
    assert fin.write_down_journal(_manual(), "P1", gl_key="GL-2100", context=CTX).amount.tolist() == [-100.0]


def test_margin_trail_marks_the_write_down_period():
    f = _full([("P1", "2025-11", 1000.0, 800.0, 200.0, 250.0, 0.0), ("P1", "2025-12", 1000.0, 1200.0, 300.0, 300.0, 50.0), ("P2", "2025-12", 5.0, 4.0, 1.0, 1.0, 0.0)])
    w = fin.write_down_journal(_manual(), "P1", context=CTX)
    t = fin.margin_trail(f.sample(frac=1, random_state=2), "P1", w, context=CTX)
    assert t.period.tolist() == ["2025-11", "2025-12"] and t.write_down_period.tolist() == [False, True] and t.write_down_amount.tolist()[1] == 100.0 and t.write_down_amount_dkk.tolist()[1] == 746.0
    assert np.isnan(t.write_down_amount.iloc[0]) and t.currency.tolist() == ["EUR", "EUR"]
    assert not fin.margin_trail(f, "P1", None, context=CTX).write_down_period.any()
    with pytest.raises(FrameError, match="P9 has no rows"):
        fin.margin_trail(f, "P9", None, context=CTX)


def test_margin_trail_null_journal_amounts_and_cent_sums():
    f = _full([("P1", "2025-11", 1000.0, 800.0, 200.0, 250.0, 0.0), ("P1", "2025-12", 1000.0, 1200.0, 300.0, 300.0, 50.0)])
    w = fin.write_down_journal(_manual(), "P1", context=CTX)
    for nulls in ({"amount": [np.nan, 3.0]}, {"amount_dkk": [3.0, np.nan]}):
        bad = pd.concat([w, w.assign(journal_no=8)], ignore_index=True).assign(**{k: v for k, v in nulls.items()})
        with pytest.raises(FrameError, match="null amount"):
            fin.margin_trail(f, "P1", bad, context=CTX)
    j = pd.concat([w.assign(amount=0.1, amount_dkk=74.6), w.assign(journal_no=8, amount=0.2, amount_dkk=149.2)], ignore_index=True)
    t = fin.margin_trail(f, "P1", j, context=CTX)
    assert t.write_down_amount_dkk.iloc[1] == 223.8 and t.write_down_amount.iloc[1] == 0.3, "sums are cut to cents, no 223.79999999999998"


def test_cost_to_completion_lists_missing_projects_with_a_reason():
    f = _pf([("P1", "2025-11", 1000.0, 800.0, 200.0, 0.0), ("P2", "2025-11", 1000.0, 900.0, 900.0, 0.0), ("P3", "2025-10", 1000.0, 900.0, 100.0, 0.0)])
    c = fin.cost_to_completion(f, ["P2", "P1", "P3"], "2025-11", context=CTX)
    assert c.prj_key.tolist() == ["P2", "P1", "P3"] and c.cost_to_completion.tolist()[:2] == [0.0, 600.0] and c.uncommitted.tolist()[:2] == [-10.0, 590.0]
    assert c.reason.tolist() == [None, None, "no finance row"] and c.eac.isna().tolist() == [False, False, True]
    with pytest.raises(FrameError, match="repeated keys"):
        fin.cost_to_completion(f, ["P1", "P1"], "2025-11", context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        fin.cost_to_completion(pd.concat([f, f.iloc[:1]]), ["P1"], "2025-11", context=CTX)


def test_order_book_check_roll_forward_and_opening():
    o = pd.DataFrame({"le_key": "LE-01", "project_type": "cable", "period": ["2023-01", "2023-02", "2023-03"], "backlog_opening": [100.0, 150.0, 120.0], "order_intake_total": [80.0, 0.0, 10.0],
                      "revenue_recognised": [30.0, 30.0, 20.0], "backlog_closing": [150.0, 120.0, 110.0]})
    assert fin.order_book_check(o, context=CTX).empty
    r = fin.order_book_check(o.assign(backlog_closing=[150.0, 120.0, 110.1]), context=CTX)
    assert r.rule.tolist() == ["roll_forward"] and r.key.tolist() == ["LE-01 cable 2023-03"]
    r2 = fin.order_book_check(o.assign(backlog_opening=[100.0, 149.9, 120.0]), context=CTX)
    assert sorted(r2.rule) == ["opening_not_previous_closing", "roll_forward"]
    assert fin.order_book_check(o.assign(backlog_closing=[150.0, 120.0, 110.04]), context=CTX).empty, "within the 0.05 tolerance"
    assert fin.order_book_check(o.sample(frac=1, random_state=1), context=CTX).empty, "input order does not matter"


def test_review_edge_cases_dates_nulls_cents_journals_and_the_order_book():
    f = _pf([("P1", "2025-03", 1000.0, 800.0, 400.0, 0.0)])
    assert fin.percent_complete(f, {"P1": pd.Timestamp("2025-03-31 14:00")}, cap=CAP, context=CTX).tolist() == [100.0], "a time of day on the last day still ends the project"
    with pytest.raises(FrameError, match="more than once"):
        fin.percent_complete(f, pd.Series([pd.Timestamp("2025-03-31")] * 2, index=["P1", "P1"]), cap=CAP, context=CTX)
    with pytest.raises(FrameError, match="none of the keys"):
        fin.percent_complete(f, pd.Series([pd.Timestamp("2025-03-31")]), cap=CAP, context=CTX)
    for bad in (None, "2025-03-15", "2025/03"):
        with pytest.raises(FrameError, match="period must be text"):
            fin.percent_complete(f.assign(period=bad), {}, cap=CAP, context=CTX)
    done = _pf([("P1", "2025-03", np.nan, np.nan, 400.0, 0.0)])
    assert fin.loss_provision(done, {"P1": "2025-03-01"}, cap=CAP, context=CTX).tolist() == [0.0], "none when done, also when the inputs are null"
    cents = _pf([("P1", "2025-03", 4582887.00, 328289.01, 9637379.55, 0.0)])
    assert fin.revenue_recognised(cents, {}, cap=0.995, context=CTX).tolist() == [4559972.56], "integer cents like the generator: rint(contract value in cents times the fraction)"
    # write-down journals
    full = _full([("P1", "2025-11", 1000.0, 800.0, 200.0, 250.0, 0.0), ("P1", "2025-12", 1000.0, 1200.0, 300.0, 300.0, 50.0)])
    one = pd.DataFrame({"posting_date": pd.to_datetime(["2025-12-01", "2025-12-18"]), "amount": [100.0, 40.0], "amount_dkk": [746.0, 298.4], "currency": "EUR"})
    t = fin.margin_trail(full, "P1", one, context=CTX)
    assert t.write_down_amount.tolist()[1] == 140.0 and t.write_down_amount_dkk.tolist()[1] == 1044.4, "two journals in one month add up"
    for wd, msg in ((one.assign(posting_date=pd.to_datetime(["2026-03-05", "2026-03-06"])), "month without a finance"), (one.assign(currency=["EUR", "DKK"]), "currency"),
                    (one.assign(posting_date=[pd.NaT, pd.Timestamp("2025-12-18")]), "no posting date")):
        with pytest.raises(FrameError, match=msg):
            fin.margin_trail(full, "P1", wd, context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        fin.margin_trail(pd.concat([full, full.iloc[1:]]), "P1", one, context=CTX)
    m = _manual().iloc[[2, 0]].assign(posting_date=["18/12/2025", "05/01/2025"], prj_key="P1")
    srt = fin.write_down_journal(m.assign(gl_key="GL-5190"), "P1", context=CTX)
    assert srt.amount.tolist() == [100.0, 5.0], "ordered by the date as a date, not as text"
    # cost to completion
    g = _pf([("P1", "2025-11", 1000.0, np.nan, 200.0, 0.0)])
    assert fin.cost_to_completion(g, ["P1"], "2025-11", context=CTX).reason.tolist() == [None], "a row with a null EAC is a row"
    assert fin.cost_to_completion(g, [], "2025-11", context=CTX).empty
    with pytest.raises(FrameError, match="period must be text"):
        fin.cost_to_completion(g, ["P1"], "2025-11-30", context=CTX)
    # order book
    o = pd.DataFrame({"le_key": "LE-01", "project_type": "cable", "period": ["2023-01", "2023-02", "2023-03"], "backlog_opening": [100.0, 150.0, 120.0], "order_intake_total": [80.0, 0.0, 10.0],
                      "revenue_recognised": [30.0, 30.0, 20.0], "backlog_closing": [150.0, 120.0, 110.0]})
    for col in ("backlog_closing", "backlog_opening", "order_intake_total", "revenue_recognised"):
        with pytest.raises(FrameError, match="null values"):
            fin.order_book_check(o.assign(**{col: [1.0, np.nan, 1.0]}), context=CTX)
    with pytest.raises(FrameError, match="skips a month"):
        fin.order_book_check(o.assign(period=["2023-01", "2023-02", "2023-05"]), context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        fin.order_book_check(pd.concat([o, o.iloc[:1]]), context=CTX)
    assert fin.order_book_check(o.assign(backlog_closing=[150.0, 120.0, 110.05]), context=CTX).empty, "exactly the tolerance is inside it"
    assert not fin.order_book_check(o.assign(backlog_closing=[150.0, 120.0, 110.06]), context=CTX).empty
    with pytest.raises(FrameError, match="tolerance"):
        fin.order_book_check(o, tolerance=-1.0, context=CTX)
    two = pd.concat([o, o.assign(project_type="duct", backlog_closing=[150.0, 120.0, 111.0])])
    assert fin.order_book_check(two, context=CTX).key.tolist() == ["LE-01 duct 2023-03"], "groups are judged apart"
