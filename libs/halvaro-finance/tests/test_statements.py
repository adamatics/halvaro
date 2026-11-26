"""Statutory statements (plan 5.6): hand built statements, then the baseline release (nine reports, ledger rebuild)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M12, M3 = Context(stage="month12", role="r"), Context(stage="month3", role="r")


def _tb():
    rows = [("LE-01", "2025-11", "GL-4000", 0.0, 100.0, -100.0), ("LE-01", "2025-12", "GL-4000", 0.0, 50.0, -50.0), ("LE-01", "2025-12", "GL-5000", 60.0, 0.0, 60.0), ("LE-01", "2025-12", "GL-5900", 5.0, 0.0, 5.0),
            ("LE-01", "2025-12", "GL-1000", 0.0, 0.0, 500.0), ("LE-01", "2025-12", "GL-2000", 0.0, 0.0, -300.0), ("LE-01", "2025-12", "GL-9999", 0.0, 0.0, 7.0), ("LE-01", "2024-12", "GL-4000", 0.0, 9.0, -9.0),
            ("LE-02", "2025-12", "GL-4000", 0.0, 1.0, -1.0)]
    return pd.DataFrame(rows, columns=["le_key", "period", "gl_key", "debit", "credit", "closing_balance"])


def _gl():
    return pd.DataFrame({"gl_key": ["GL-4000", "GL-5000", "GL-5900", "GL-1000", "GL-2000", "GL-9999"], "statement": ["IS", "IS", "IS", "BS", "BS", "BS"],
                         "dk_statutory_map": ["DK-IS-REV", "DK-IS-COS", None, "DK-BS-CASH", "DK-BS-TRADE_P", None], "de_statutory_map": ["DE-IS-REV", "DE-IS-COS", None, "DE-BS-CASH", "DE-BS-TRADE_P", None]})


def _map():
    return pd.DataFrame({"map_code": ["DK-IS-REV", "DK-IS-COS", "DK-BS-CASH", "DK-BS-TRADE_P", "DE-IS-REV"], "line_code": ["REV", "COS", "CASH", "TRADE_P", "REV"],
                         "statement": ["IS", "IS", "BS", "BS", "IS"], "normal_side": ["credit", "debit", "debit", "credit", "credit"]})


def test_statement_from_ledger_signs_periods_and_unmapped_accounts():
    r = fin.statement_from_ledger(_tb(), _gl(), _map(), "LE-01", "DK", 2025, require_full_year=False, context=M12)
    lines = r.lines.set_index("map_code")
    assert lines.loc["DK-IS-REV", "amount"] == 150.0 and lines.loc["DK-IS-COS", "amount"] == -60.0, "income statement: credit less debit over the periods of the year, costs negative"
    assert lines.loc["DK-BS-CASH", "amount"] == 500.0 and lines.loc["DK-BS-TRADE_P", "amount"] == 300.0, "balance sheet: closing balance of the last period, liabilities positive"
    assert lines.loc["DK-IS-REV", "line_code"] == "REV" and lines.loc["DK-BS-CASH", "statement"] == "balance_sheet" and lines.loc["DK-IS-REV", "n_accounts"] == 1
    assert r.pbt == 90.0 and list(r.unmapped.gl_key) == ["GL-5900", "GL-9999"] and r.unmapped.kind.tolist() == ["income_statement", "balance_sheet"], "accounts with a balance and no map are listed, not hidden"
    assert fin.statement_from_ledger(_tb(), _gl(), _map(), "LE-02", "DE", 2025, require_full_year=False, context=M12).lines.amount.tolist() == [1.0]
    for args, msg in ((("LE-01", "FR", 2025), "DK or DE"), (("LE-01", "DK", "2025"), "whole year"), (("LE-09", "DK", 2025), "no trial balance rows"), (("LE-01", "DK", 2030), "no trial balance rows")):
        with pytest.raises(FrameError, match=msg):
            fin.statement_from_ledger(_tb(), _gl(), _map(), *args, require_full_year=False, context=M12)
    for kw, msg in ((dict(trial_balance=pd.concat([_tb(), _tb().iloc[:1]])), "unique keys"), (dict(trial_balance=_tb().assign(debit=np.nan)), "null amounts"),
                    (dict(gl_account=_gl().iloc[1:]), "not in finance.gl_account"), (dict(statutory_map_line=_map().iloc[1:]), "not in finance.statutory_map_line")):
        a = dict(trial_balance=_tb(), gl_account=_gl(), statutory_map_line=_map())
        a.update(kw)
        with pytest.raises(FrameError, match=msg):
            fin.statement_from_ledger(a["trial_balance"], a["gl_account"], a["statutory_map_line"], "LE-01", "DK", 2025, require_full_year=False, context=M12)


def _set(**over):
    """One report with the codes of the German layout: income statement, balance sheet, cash flow and equity that foot and link."""
    v = {"REV": 1000.0, "OOI": 10.0, "COS": -600.0, "EXT": -50.0, "STAFF": -200.0, "DEP": -40.0, "OOE": -10.0, "EBIT": 110.0, "FININC": 5.0, "FINEXP": -15.0, "PBT": 100.0, "TAX": -30.0, "NI": 70.0,
         "FA_TANG": 300.0, "FA_TOT": 300.0, "INVT": 100.0, "CASH": 200.0, "CA_TOT": 300.0, "TA": 600.0, "EQ_SC": 100.0, "EQ_RE": 250.0, "EQ_TOT": 350.0, "PROV": 50.0, "PROV_TOT": 50.0,
         "TRADE_P": 200.0, "CL_TOT": 200.0, "LIAB_TOT": 200.0, "TEL": 600.0,
         "CF_EBIT": 110.0, "CF_OPS": 110.0, "CF_OPA": 100.0, "CF_FININC": 5.0, "CF_FINEXP": -15.0, "CF_CAPEX_T": -40.0, "CF_INVA": -40.0, "CF_EQ": 0.0, "CF_FINA": 0.0, "CF_NET": 60.0, "CF_OPEN": 140.0, "CF_CLOSE": 200.0,
         "OPEN_SC": 100.0, "OPEN_RE": 180.0, "OPEN_TOT": 280.0, "DIVPAID_SC": 0.0, "DIVPAID_RE": 0.0, "DIVPAID_TOT": 0.0, "RESULT_SC": 0.0, "RESULT_RE": 70.0, "RESULT_TOT": 70.0, "CLOSE_SC": 100.0, "CLOSE_RE": 250.0, "CLOSE_TOT": 350.0}
    v.update(over)
    stmt = {k: "income_statement" for k in "REV OOI COS EXT STAFF DEP OOE EBIT FININC FINEXP PBT TAX NI".split()}
    stmt.update({k: "cash_flow" for k in v if k.startswith("CF_")})
    stmt.update({k: "equity" for k in v if k.split("_")[0] in ("OPEN", "DIVPAID", "RESULT", "CLOSE")})
    rows = [("RPT-1", stmt.get(k, "balance_sheet"), i, k, a, 140.0 if k == "CASH" else np.nan, "line") for i, (k, a) in enumerate(v.items())]
    return pd.DataFrame(rows, columns=["rpt_key", "statement", "line_no", "line_code", "amount", "prior_year_amount", "line_type"])


def test_statements_check_clean_set_and_every_rule_fires():
    assert fin.statements_check(_set(), context=M12).empty
    rule = lambda **o: sorted(set(fin.statements_check(_set(**o), context=M12).rule))
    assert rule(REV=1000.5) == ["foot"] and rule(REV=1000.005) == [], "footing is within the tolerance of 0.011"
    assert rule(TA=601.0) == ["balance_sheet_balances", "foot"]
    assert rule(CF_CLOSE=201.0) == ["cash_flow_ends_at_cash", "foot"]
    assert rule(CLOSE_TOT=351.0, CLOSE_RE=251.0) == ["equity_ends_at_balance_sheet", "equity_rolls"]
    assert rule(RESULT_TOT=71.0, RESULT_RE=71.0) == ["equity_result_is_net_income", "equity_rolls"]
    assert rule(CF_OPEN=141.0) == ["cash_flow_opens_at_prior_cash", "foot"]
    with_gp = pd.concat([_set(), pd.DataFrame([("RPT-1", "income_statement", 99, "GP", 360.0, np.nan, "subtotal")], columns=_set().columns)], ignore_index=True)
    assert fin.statements_check(with_gp, context=M12).empty, "with a GP line EBIT foots from it: 360 - 200 - 40 - 10"
    bad_gp = with_gp.assign(amount=with_gp.amount.where(with_gp.line_code != "GP", 365.0))
    assert set(fin.statements_check(bad_gp, context=M12).key) == {"RPT-1 GP", "RPT-1 EBIT"}
    assert fin.statements_check(_set().iloc[:0], context=M12).empty
    with pytest.raises(FrameError, match="more than one row"):
        fin.statements_check(pd.concat([_set(), _set().iloc[:1]]), context=M12)
    with pytest.raises(FrameError, match="tolerance"):
        fin.statements_check(_set(), tolerance=-1, context=M12)
    notes = pd.concat([_set(), pd.DataFrame([("RPT-1", "notes", 1, "REV", 5.0, np.nan, "note")], columns=_set().columns)])
    assert fin.statements_check(notes, context=M12).empty, "notes lines are not statements"


def _reports():
    return pd.DataFrame({"rpt_key": ["R23", "R24", "R25", "G24"], "le_key": ["LE-01", "LE-01", "LE-01", None], "scope": ["entity", "entity", "entity", "group"], "fiscal_year": [2023, 2024, 2025, 2024]})


def _lines(prior):
    rows = []
    for rk, rev, pri in (("R23", 100.0, np.nan), ("R24", 120.0, prior[0]), ("R25", 140.0, prior[1]), ("G24", 500.0, np.nan)):
        rows += [(rk, "income_statement", 1, "REV", rev, pri), (rk, "balance_sheet", 2, "TA", rev * 10, pri * 10 if pd.notna(pri) else 7.0)]
    return pd.DataFrame(rows, columns=["rpt_key", "statement", "line_no", "line_code", "amount", "prior_year_amount"])


def test_prior_year_column_equals_the_previous_report_and_the_first_year_has_none():
    assert fin.prior_year_column(_lines((100.0, 120.0)), _reports(), context=M12).empty, "the first year balance sheet prior is the opening balance and is not checked"
    r = fin.prior_year_column(_lines((100.0, 119.0)), _reports(), context=M12)
    assert r.rule.tolist() == ["prior_year_differs", "prior_year_differs"] and set(r.key) == {"R25 REV", "R25 TA"}
    first = _lines((100.0, 120.0)).assign(prior_year_amount=lambda d: d.prior_year_amount.where(d.rpt_key != "R23", 5.0))
    assert set(fin.prior_year_column(first, _reports(), context=M12).rule) == {"first_year_prior"} and fin.prior_year_column(first, _reports(), context=M12).key.tolist() == ["R23 REV"]
    missing = _lines((np.nan, 120.0))
    assert set(fin.prior_year_column(missing, _reports(), codes=("REV",), context=M12).rule) == {"prior_year_missing"}
    assert fin.prior_year_column(_lines((100.0, 120.0)), _reports(), codes=("TA",), context=M12).empty
    assert fin.prior_year_column(_lines((100.0, 120.004)), _reports(), codes=("REV",), context=M12).empty, "within 0.005"
    for bad, msg in ((_reports().assign(rpt_key="R"), "more than one row"), (pd.concat([_reports(), _reports().iloc[:1].assign(rpt_key="X")]), "two reports of the same")):
        with pytest.raises(FrameError, match=msg):
            fin.prior_year_column(_lines((100.0, 120.0)), bad, context=M12)


def test_filing_status_and_size_class_use_the_danish_facts():
    months = int(fact("frep.annual_reports.DK.filing_deadline_months_after_year_end").value)
    sr = pd.DataFrame({"rpt_key": ["A", "B", "C", "D"], "le_key": ["LE-01", None, "LE-02", "LE-01"], "period_end": ["2025-12-31"] * 4,
                       "filing_deadline": ["2026-05-31", "2026-05-31", "2026-12-31", "2026-05-31"], "filed_date": ["2026-05-21", "2026-06-02", "2026-12-01", None], "filed_on_time": [True, False, True, None]})
    f = fin.filing_status(sr, context=M12).value.set_index("rpt_key")
    assert months == 5 and f.loc["A", ["rule_agrees", "days_late", "status", "filed_on_time_agrees"]].tolist() == [True, -10, "on_time", True]
    assert f.loc["B", ["days_late", "status"]].tolist() == [2, "late"] and f.loc["B", "rule_agrees"] and pd.isna(f.loc["C", "rule_agrees"]) and pd.isna(f.loc["C", "deadline_rule"]), "German entities have no fact: not checked"
    assert f.loc["D", "status"] == "not_filed" and f.loc["D", "filed_on_time_agrees"]
    wrong = fin.filing_status(sr.assign(filing_deadline=["2026-04-30"] + ["2026-05-31"] * 3), context=M12).value.set_index("rpt_key")
    assert not wrong.loc["A", "rule_agrees"]
    assert not fin.filing_status(sr.assign(filed_on_time=[False, False, True, None]), context=M12).value.set_index("rpt_key").loc["A", "filed_on_time_agrees"]
    with pytest.raises(FrameError, match="more than one row"):
        fin.filing_status(pd.concat([sr, sr.iloc[:1]]), context=M12)
    rep = pd.DataFrame({"rpt_key": ["A", "B", "C"], "le_key": ["LE-01", None, "LE-02"], "revenue": [4e8, 2e8, 4e8], "total_assets": [1e8, 2e8, 1e8], "average_employees": [300.0, 200.0, 300.0], "size_criteria_met": [2, 1, 2]})
    s = fin.size_class(rep, context=M12).value.set_index("rpt_key")
    assert s.loc["A", ["revenue_over", "assets_over", "employees_over", "criteria_exceeded", "agrees"]].tolist() == [True, False, True, 2.0, True]
    assert s.loc["B", "criteria_exceeded"] == 1.0 and s.loc["B", "agrees"], "the group is judged by the Danish thresholds"
    assert np.isnan(s.loc["C", "criteria_exceeded"]) and pd.isna(s.loc["C", "agrees"]), "no German thresholds"
    assert not fin.size_class(rep.assign(size_criteria_met=[3, 1, 2]), context=M12).value.set_index("rpt_key").loc["A", "agrees"]
    assert fin.size_class(rep.assign(revenue=[3e8, 3e8 + 1, 3e8], total_assets=[1.5e8, 1.5e8 + 1, 0], average_employees=[250.0, 250.1, 0]), context=M12).value.criteria_exceeded.tolist()[:2] == [0.0, 3.0], "strictly above the thresholds"
    with pytest.raises(FrameError, match="null revenue"):
        fin.size_class(rep.assign(revenue=np.nan), context=M12)


def test_statements_check_nulls_link_tolerance_and_inputs():
    rule = lambda **o: sorted(set(fin.statements_check(_set(**o), context=M12).rule))
    assert rule(TEL=600.008) == ["balance_sheet_balances"], "a link break of 0.008 is above the link tolerance 0.005 and inside the footing tolerance"
    assert rule(TEL=600.004) == [] and fin.statements_check(_set(TEL=600.008), link_tolerance=0.01, context=M12).empty
    for code in ("TEL", "CF_CLOSE", "OPEN_TOT", "TA", "CASH"):
        d = fin.statements_check(_set(**{code: np.nan}), context=M12)
        assert "null_amount" in set(d.rule) and f"RPT-1 {code}" in set(d.key), f"a null {code} is reported, it does not make the check pass"
    gp = pd.concat([_set(), pd.DataFrame([("RPT-1", "income_statement", 99, "GP", np.nan, np.nan, "subtotal")], columns=_set().columns)], ignore_index=True)
    assert set(fin.statements_check(gp, context=M12).rule) == {"null_amount"}, "a GP row with a null amount does not break the EBIT footing"
    for bad in (np.nan, -1, True):
        with pytest.raises(FrameError, match="link_tolerance"):
            fin.statements_check(_set(), link_tolerance=bad, context=M12)
    with pytest.raises(FrameError, match="rpt_key"):
        fin.statements_check(_set().assign(rpt_key=lambda d: d.rpt_key.where(d.index != 0, None)), context=M12)


def test_prior_year_column_inputs_gaps_and_null_previous_amounts():
    for kw in (dict(tolerance=np.nan), dict(tolerance=-1), dict(tolerance=True), dict(codes="REV")):
        with pytest.raises(FrameError):
            fin.prior_year_column(_lines((100.0, 120.0)), _reports(), context=M12, **kw)
    prev_null = _lines((100.0, 120.0)).assign(amount=lambda d: d.amount.where(~((d.rpt_key == "R24") & (d.line_code == "REV")), np.nan))
    r = fin.prior_year_column(prev_null, _reports(), codes=("REV",), context=M12)
    assert r.key.tolist() == ["R25 REV"] and r.rule.tolist() == ["prior_year_missing"], "a null amount on the previous report is not a pass"
    gap = _reports().iloc[[0, 2]]
    legit = _lines((100.0, 120.0)).assign(prior_year_amount=lambda d: d.prior_year_amount.where(d.rpt_key != "R25", 120.0))
    assert fin.prior_year_column(legit, gap, context=M12).empty, "after a gap in the years a report is not a first year and has nothing to compare with"
    for bad in (_reports().assign(fiscal_year=pd.array([2023, 2024, pd.NA, 2024], dtype="Int64")), _reports().assign(fiscal_year=["2023", "2024", "2025", "2024"])):
        with pytest.raises(FrameError, match="fiscal_year"):
            fin.prior_year_column(_lines((100.0, 120.0)), bad, context=M12)
    cat = _reports().assign(le_key=_reports().le_key.astype("category"))
    assert fin.prior_year_column(_lines((100.0, 120.0)), cat, context=M12).empty


def test_ledger_rounding_drops_and_inputs():
    k = dict(require_full_year=False, context=M12)
    half = _tb().assign(credit=lambda d: d.credit.where(~((d.period == "2025-12") & (d.gl_key == "GL-4000")), 50.125))
    assert fin.statement_from_ledger(half, _gl(), _map(), "LE-01", "DK", 2025, **k).lines.set_index("map_code").loc["DK-IS-REV", "amount"] == 150.13, "half a cent rounds away from zero in integer cents"
    with pytest.raises(FrameError, match="without a period"):
        fin.statement_from_ledger(_tb().assign(period=lambda d: d.period.where(d.index != 1, None)), _gl(), _map(), "LE-01", "DK", 2025, **k)
    with pytest.raises(FrameError, match="like 2025-03"):
        fin.statement_from_ledger(_tb().assign(period=lambda d: d.period.where(d.index != 1, "2025-9")), _gl(), _map(), "LE-01", "DK", 2025, **k)
    only_nov = _tb().assign(period=lambda d: d.period.where(~((d.gl_key == "GL-1000")), "2025-11"))
    with pytest.raises(FrameError, match="no row in the last period"):
        fin.statement_from_ledger(only_nov, _gl(), _map(), "LE-01", "DK", 2025, **k)
    zero = only_nov.assign(closing_balance=lambda d: d.closing_balance.where(d.gl_key != "GL-1000", 0.0))
    assert "DK-BS-CASH" not in set(fin.statement_from_ledger(zero, _gl(), _map(), "LE-01", "DK", 2025, **k).lines.map_code), "an account omitted at a zero balance counts nothing"
    with pytest.raises(FrameError, match="IS or BS"):
        fin.statement_from_ledger(_tb(), _gl().assign(statement=["PL", "IS", "IS", "BS", "BS", "BS"]), _map(), "LE-01", "DK", 2025, **k)
    for side in ("CREDIT", None):
        with pytest.raises(FrameError, match="normal_side"):
            fin.statement_from_ledger(_tb(), _gl(), _map().assign(normal_side=[side, "debit", "debit", "credit", "credit"]), "LE-01", "DK", 2025, **k)
    with pytest.raises(FrameError, match="not twelve"):
        fin.statement_from_ledger(_tb(), _gl(), _map(), "LE-01", "DK", 2025, context=M12)
    cat = _gl().assign(dk_statutory_map=_gl().dk_statutory_map.astype("category"))
    assert fin.statement_from_ledger(_tb(), cat, _map(), "LE-01", "DK", 2025, **k).pbt == 90.0
    with pytest.raises(FrameError, match="join on gl_key"):
        fin.statement_from_ledger(_tb(), _gl().assign(gl_key=range(6)), _map(), "LE-01", "DK", 2025, **k)


def test_filing_status_edges_envelope_and_group_keys():
    base = pd.DataFrame({"rpt_key": ["A"], "le_key": ["LE-01"], "period_end": ["2025-12-31"], "filing_deadline": ["2026-05-31"], "filed_date": ["2026-05-31 10:00"], "filed_on_time": [True]})
    r = fin.filing_status(base, context=M12)
    assert r.status == "VERIFY" and r.facts_used[0][0] == "frep.annual_reports.DK.filing_deadline_months_after_year_end", "the fact status is carried"
    v = r.value.iloc[0]
    assert (v.status, v.days_late, bool(v.filed_on_time_agrees), bool(v.rule_agrees)) == ("on_time", 0, True, True), "a filing with a time of day on the deadline day is on time"
    assert fin.filing_status(base.assign(filing_deadline="2026-05-31 23:59:59"), context=M12).value.iloc[0].days_late == 0
    late = fin.filing_status(base.assign(filed_date="2026-06-01"), context=M12).value.iloc[0]
    assert (late.status, late.days_late) == ("late", 1)
    nd = fin.filing_status(base.assign(filing_deadline=None), context=M12).value.iloc[0]
    assert nd.status == "no_deadline" and pd.isna(nd.days_late), "a missing deadline is not late"
    feb = fin.filing_status(base.assign(period_end="2025-02-28", filing_deadline="2025-07-31"), context=M12).value.iloc[0]
    assert str(feb.deadline_rule.date()) == "2025-07-31" and bool(feb.rule_agrees), "a month end year end has a month end deadline"
    nope = fin.filing_status(base.assign(period_end=None), context=M12).value.iloc[0]
    assert pd.isna(nope.rule_agrees), "a null period end is not judged"
    grp = pd.concat([base, base.assign(rpt_key="G", le_key=None), base.assign(rpt_key="DE", le_key="LE-02")], ignore_index=True)
    for dtype in (object, "string", "category"):
        v = fin.filing_status(grp.assign(le_key=grp.le_key.astype(dtype)), context=M12).value.set_index("rpt_key")
        assert bool(v.loc["G", "rule_agrees"]) and pd.isna(v.loc["DE", "rule_agrees"]), dtype
    with pytest.raises(FrameError, match="dk_entities"):
        fin.filing_status(base, dk_entities="LE-01", context=M12)


def test_size_class_edges_envelope_and_group_keys():
    t = [3e8, 1.5e8, 250.0]
    rep = pd.DataFrame({"rpt_key": ["A", "B", "G", "DE"], "le_key": ["LE-01", "LE-01", None, "LE-02"], "revenue": [t[0], t[0] + 1, t[0] + 1, np.nan], "total_assets": [t[1], t[1], t[1] + 1, 5.0],
                        "average_employees": [t[2], t[2] + 1, t[2], 1.0], "size_criteria_met": [0, 2, 2, None]})
    r = fin.size_class(rep, context=M12)
    assert r.status == "VERIFY" and len(r.facts_used) == 3
    v = r.value.set_index("rpt_key")
    assert v.loc["A", ["revenue_over", "assets_over", "employees_over", "criteria_exceeded"]].tolist() == [False, False, False, 0.0], "a value at a threshold does not exceed it"
    assert v.loc["B", ["revenue_over", "assets_over", "employees_over"]].tolist() == [True, False, True] and v.loc["G", ["revenue_over", "assets_over", "employees_over"]].tolist() == [True, True, False]
    assert v.agrees[["A", "B", "G"]].tolist() == [True, True, True] and pd.isna(v.loc["DE", "agrees"]) and pd.isna(v.loc["DE", "criteria_exceeded"]), "German rows are listed, not judged, and may have nulls"
    assert pd.isna(fin.size_class(rep.assign(size_criteria_met=[None, 2, 2, None]), context=M12).value.set_index("rpt_key").loc["A", "agrees"]), "a null stored count is not a disagreement"
    for dtype in ("string", "category"):
        assert fin.size_class(rep.assign(le_key=rep.le_key.astype(dtype)), context=M12).value.criteria_exceeded.tolist()[:3] == [0.0, 2.0, 2.0], dtype
    with pytest.raises(FrameError, match="dk_entities"):
        fin.size_class(rep, dk_entities="LE-01", context=M12)
    with pytest.raises(FrameError, match="null revenue"):
        fin.size_class(rep.assign(revenue=np.nan), context=M12)


def test_round2_ledger_unmapped_signs_zero_net_inf_and_wrong_statement():
    k = dict(require_full_year=False, context=M12)
    r = fin.statement_from_ledger(_tb(), _gl(), _map(), "LE-01", "DK", 2025, **k)
    un = r.unmapped.set_index("gl_key")["amount_debit_positive_for_bs"]
    assert un["GL-5900"] == -5.0 and un["GL-9999"] == 7.0, "income statement accounts credit less debit, balance sheet accounts the closing balance"
    two = pd.concat([_tb(), pd.DataFrame([("LE-01", "2025-11", "GL-5900", 0.0, 5.0, -5.0)], columns=_tb().columns)], ignore_index=True)
    assert "GL-5900" not in set(fin.statement_from_ledger(two, _gl(), _map(), "LE-01", "DK", 2025, **k).unmapped.gl_key), "an account that nets to zero over the periods is not listed"
    for v in (np.inf, -np.inf, 1e17):
        with pytest.raises(FrameError, match="finite"):
            fin.statement_from_ledger(_tb().assign(credit=lambda d: d.credit.where(d.index != 1, v)), _gl(), _map(), "LE-01", "DK", 2025, **k)
    with pytest.raises(FrameError, match="other statement"):
        fin.statement_from_ledger(_tb(), _gl(), _map().assign(statement=["BS", "IS", "BS", "BS", "IS"]), "LE-01", "DK", 2025, **k)
    liab = _tb().assign(period=lambda d: d.period.where(d.gl_key != "GL-2000", "2025-11"))
    with pytest.raises(FrameError, match="no row in the last period"):
        fin.statement_from_ledger(liab, _gl(), _map(), "LE-01", "DK", 2025, **k)
    tax_gl = _gl().assign(dk_statutory_map=["DK-IS-REV", "DK-IS-COS", "DK-IS-TAX", "DK-BS-CASH", "DK-BS-TRADE_P", None])
    tax_map = pd.concat([_map(), pd.DataFrame({"map_code": ["DK-IS-TAX"], "line_code": ["TAX"], "statement": ["IS"], "normal_side": ["debit"]})], ignore_index=True)
    t = fin.statement_from_ledger(_tb(), tax_gl, tax_map, "LE-01", "DK", 2025, **k)
    assert t.lines.set_index("line_code").loc["TAX", "amount"] == -5.0 and t.pbt == 90.0, "tax is a line but not part of pbt"
    eleven = _tb().iloc[:1]
    many = pd.concat([_tb().assign(period="2025-%02d" % m) .drop_duplicates(["gl_key"]) for m in range(1, 12)], ignore_index=True)
    with pytest.raises(FrameError, match="not twelve"):
        fin.statement_from_ledger(many, _gl(), _map(), "LE-01", "DK", 2025, context=M12)


def test_round2_checks_equity_roll_without_dividends_and_tolerances():
    nodiv = _set()[~_set().line_code.str.startswith("DIVPAID")]
    assert fin.statements_check(nodiv, context=M12).empty, "no dividend lines: the roll is open + result = close"
    broken = nodiv.assign(amount=lambda d: d.amount.where(~d.line_code.isin(["OPEN_TOT", "OPEN_RE"]), d.amount + 1000))
    assert "equity_rolls" in set(fin.statements_check(broken, context=M12).rule)
    # the roll and the opening cash use the link tolerance 0.005, the footing 0.011
    assert fin.statements_check(_set(OPEN_TOT=280.008, OPEN_RE=180.008), context=M12).rule.tolist() == ["equity_rolls"], "0.008 off in the roll: above 0.005, inside the footing tolerance"
    assert fin.statements_check(_set(CF_OPEN=140.008), context=M12).rule.tolist() == ["cash_flow_opens_at_prior_cash"], "0.008 off the prior cash: above 0.005, the footing of CF_CLOSE (0.008) is inside 0.011"
    assert fin.statements_check(_set(OPEN_TOT=280.004, OPEN_RE=180.004), context=M12).empty


def test_round2_prior_year_iterator_codes_size_text_and_filing_dtypes():
    r = fin.prior_year_column(_lines((100.0, 119.0)), _reports(), codes=iter(["REV"]), context=M12)
    assert r.key.tolist() == ["R25 REV"], "an iterator of codes is read once, not consumed by the check"
    rep = pd.DataFrame({"rpt_key": ["A"], "le_key": ["LE-01"], "revenue": ["n/a"], "total_assets": [1.0], "average_employees": [1.0], "size_criteria_met": [0]})
    with pytest.raises(FrameError, match="numbers"):
        fin.size_class(rep, context=M12)
    base = pd.DataFrame({"rpt_key": ["A", "B"], "le_key": ["LE-01", "LE-01"], "period_end": ["2025-12-31", "2025-11-30"], "filing_deadline": ["2026-05-31", None], "filed_date": ["2026-05-01", "2026-06-01"], "filed_on_time": [True, True]})
    v = fin.filing_status(base, context=M12).value.set_index("rpt_key")
    assert pd.isna(v.loc["B", "rule_agrees"]) and pd.isna(v.loc["B", "filed_on_time_agrees"]) and v.loc["B", "status"] == "no_deadline"
    assert str(v.days_late.dtype) == "Int64" and str(v.filed_on_time_agrees.dtype) == "boolean" and str(v.rule_agrees.dtype) == "boolean"
    clean = fin.filing_status(base.iloc[:1], context=M12).value
    assert str(clean.days_late.dtype) == "Int64" and str(clean.filed_on_time_agrees.dtype) == "boolean", "the dtypes do not depend on the data"
    ne = fin.filing_status(base.iloc[:1].assign(period_end="2025-12-15", filing_deadline="2026-05-15"), context=M12).value.iloc[0]
    assert str(ne.deadline_rule.date()) == "2026-05-15" and bool(ne.rule_agrees), "a period end that is not a month end keeps its day"
    nonDK = fin.size_class(pd.DataFrame({"rpt_key": ["D"], "le_key": ["LE-02"], "revenue": [1e12], "total_assets": [1e12], "average_employees": [1e6], "size_criteria_met": [3]}), context=M12).value
    assert nonDK[["revenue_over", "assets_over", "employees_over", "agrees"]].isna().all(axis=None), "a report outside dk_entities is not judged"
