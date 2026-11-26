"""Third round of L4.3 (mutation check): one test for each input check of the branch that no other test caught when the check was removed or loosened.

Wrong inputs are plainly wrong (text where a number is wanted, infinity, a number where a date is wanted); each must raise the library error with a message that names the argument. A valid input
beside it still works, with the number worked by hand.
"""
import datetime as dt

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, PeriodError

M12 = Context(stage="month12", role="analyst")
M3 = Context(stage="month3", role="analyst")


# statement_from_ledger: debit, credit and closing_balance are all checked

def _ledger(**over):
    tb = pd.DataFrame({"le_key": ["LE-A", "LE-A"], "period": ["2026-01", "2026-01"], "gl_key": ["GL-4000", "GL-1000"], "debit": [0.0, 500.0], "credit": [500.0, 0.0], "closing_balance": [-500.0, 500.0]})
    tb = tb.assign(**over)
    gl = pd.DataFrame({"gl_key": ["GL-4000", "GL-1000"], "statement": ["IS", "BS"], "dk_statutory_map": ["M-REV", "M-CASH"]})
    ml = pd.DataFrame({"map_code": ["M-REV", "M-CASH"], "line_code": ["REV", "CASH"], "statement": ["IS", "BS"], "normal_side": ["credit", "debit"]})
    return fin.statement_from_ledger(tb, gl, ml, "LE-A", "DK", 2026, require_full_year=False, context=M12)


def test_ledger_valid_numbers_and_numeric_text_still_work():
    assert _ledger().lines["amount"].tolist() == [500.0, 500.0]
    assert _ledger(debit=["0", "500"]).pbt == 500.0


@pytest.mark.parametrize("column", ["debit", "credit", "closing_balance"])
def test_ledger_names_the_column_that_holds_text(column):
    with pytest.raises(FrameError, match=rf"finance\.trial_balance\.{column} must hold numbers, not 'abc'"):
        _ledger(**{column: [1.0, "abc"]})


# supplier_spend: the message names start or end, whichever is wrong

def _spend(start, end):
    inv = pd.DataFrame({"sup_key": ["SUP-1"] * 2, "invoice_type": ["invoice", "credit_note"], "invoice_date": ["2026-01-05", "2026-01-20"], "net_amount_dkk": [100.0, 30.0]})
    sup = pd.DataFrame({"sup_key": ["SUP-1"], "category": ["steel"]})
    return fin.supplier_spend(inv, sup, start, end, context=M12)


def test_supplier_spend_valid_dates_still_work():
    assert _spend(dt.date(2026, 1, 1), "2026-01-31").values.tolist() == [["SUP-1", "steel", 2, 70.0]]


@pytest.mark.parametrize("which, start, end", [("start", 5, "2026-01-31"), ("end", "2026-01-01", 5)])
def test_supplier_spend_number_names_the_argument(which, start, end):
    with pytest.raises(PeriodError, match=rf"^{which} 5 is a number, not a date"):
        _spend(start, end)


@pytest.mark.parametrize("which, start, end", [("start", "not a day", "2026-01-31"), ("end", "2026-01-01", "not a day")])
def test_supplier_spend_unreadable_text_names_the_argument(which, start, end):
    with pytest.raises(PeriodError, match=rf"^{which} 'not a day' is not a date"):
        _spend(start, end)


@pytest.mark.parametrize("which, start, end", [("start", pd.Timestamp("2026-01-01", tz="UTC"), "2026-01-31"), ("end", "2026-01-01", pd.Timestamp("2026-01-31", tz="UTC"))])
def test_supplier_spend_time_zone_names_the_argument(which, start, end):
    with pytest.raises(PeriodError, match=rf"^{which} .* is not a date without a time zone"):
        _spend(start, end)


# committed_cost: an infinite quantity and an infinite price of either sign are refused, each by its own name

def _committed(qty, price):
    open_lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "prj_key": ["PRJ-1"], "qty_open": [qty]})
    lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "unit_price": [price], "currency": ["DKK"], "cst_key": ["CST-1"]})
    orders = pd.DataFrame({"po_key": ["PO-1"], "delivery_type": ["project_site"]})
    return fin.committed_cost(open_lines, lines, orders, context=M12)


def test_committed_cost_finite_values_still_work():
    assert _committed(4.0, 25.0)["committed_dkk"].tolist() == [100.0]


def test_committed_cost_infinite_quantity_names_qty_open():
    with pytest.raises(FrameError, match="^qty_open must be finite, not infinity"):
        _committed(float("inf"), 25.0)


def test_committed_cost_minus_infinite_price_names_unit_price():
    with pytest.raises(FrameError, match="^unit_price must be finite, not infinity"):
        _committed(4.0, float("-inf"))


# employer_oncosts: a missing value of pandas (pd.NA) in gross_salary is reported as a null by the number check

def test_employer_oncosts_null_gross_salary_is_a_null_not_text():
    gross = pd.DataFrame({"le_key": ["LE-A"], "cc_key": ["CC-1"], "period": ["2026-01"], "gross_salary": pd.Series([pd.NA], dtype=object)})
    with pytest.raises(FrameError, match="gross_salary has a null; it must hold numbers"):
        fin.employer_oncosts(gross, country_of={"LE-A": "DK"}, context=M12)


# labour_absorption_check: amount_dkk is checked as well as amount

def _jl(**over):
    rows = [("LE-01", "2025-01", "GL-6100", 100.0, 100.0), ("LE-01", "2025-01", "GL-7900", -100.0, -100.0), ("LE-01", "2025-01", "GL-6610", 90.0, 90.0), ("LE-01", "2025-01", "GL-7910", -100.0, -100.0)]
    return pd.DataFrame(rows, columns=["le_key", "period", "gl_key", "amount", "amount_dkk"]).assign(**over)


def test_labour_absorption_valid_amount_dkk_still_works():
    # service 90 of 100 absorbed, the rest is 10 percent of 100: inside the default share of 20 percent
    assert fin.labour_absorption_check(_jl(), max_warranty_share=0.2, context=M12).empty


def test_labour_absorption_text_in_amount_dkk_names_the_column():
    with pytest.raises(FrameError, match=r"finance\.journal_line\.amount_dkk must hold numbers, not 'abc'"):
        fin.labour_absorption_check(_jl(amount_dkk=[100.0, -100.0, "abc", -100.0]), context=M12)


# cost_per_metre_by_cost_code: each of the three number checks, with its own frame name

def _cpm(cb=None, project=None, route_change=None):
    cs = pd.DataFrame({"prj_key": ["PRJ-A"], "legacy": [False]})
    base_cb = pd.DataFrame({"prj_key": ["PRJ-A"], "period": ["2026-01"], "cst_key": ["CST-1"], "currency": ["DKK"], "actual_amount": [500.0], "incurred_in_period": [500.0], "estimate_amount": [600.0]})
    base_pr = pd.DataFrame({"prj_key": ["PRJ-A"], "route_length_m": [100.0]})
    return fin.cost_per_metre_by_cost_code(cs, base_cb if cb is None else cb, base_pr if project is None else project, route_change=route_change, context=M12)


def test_cost_per_metre_valid_route_change_is_used():
    # as built length 50 m replaces 100 m planned: 500 / 50
    r = _cpm(route_change=pd.DataFrame({"prj_key": ["PRJ-A"], "as_built_length_m": [50.0]}))
    assert r.per_project["per_metre"].tolist() == [10.0]
    assert r.per_project["route_source"].tolist() == ["as_built"]


def test_cost_per_metre_text_as_built_length_names_the_route_change_frame():
    with pytest.raises(FrameError, match=r"grid route_change frame\.as_built_length_m must hold numbers, not 'abc'"):
        _cpm(route_change=pd.DataFrame({"prj_key": ["PRJ-A"], "as_built_length_m": ["abc"]}))


def test_cost_per_metre_null_as_built_length_is_a_null():
    with pytest.raises(FrameError, match=r"grid route_change frame\.as_built_length_m has a null; it must hold numbers"):
        _cpm(route_change=pd.DataFrame({"prj_key": ["PRJ-A"], "as_built_length_m": pd.Series([pd.NA], dtype=object)}))


def test_cost_per_metre_text_route_length_names_the_project_frame():
    with pytest.raises(FrameError, match=r"projects\.project\.route_length_m must hold numbers, not 'abc'"):
        _cpm(project=pd.DataFrame({"prj_key": ["PRJ-A"], "route_length_m": ["abc"]}))


def test_cost_per_metre_text_actual_amount_names_the_breakdown():
    cb = pd.DataFrame({"prj_key": ["PRJ-A"], "period": ["2026-01"], "cst_key": ["CST-1"], "currency": ["DKK"], "actual_amount": ["abc"], "incurred_in_period": [500.0], "estimate_amount": [600.0]})
    with pytest.raises(FrameError, match=r"finance\.project_cost_breakdown\.actual_amount must hold numbers, not 'abc'"):
        _cpm(cb=cb)


# margin_trail: the frame needs a period column

def test_margin_trail_without_period_names_the_column():
    pf = pd.DataFrame({"prj_key": ["PRJ-1"], "currency": ["EUR"], "contract_value": [1000.0], "eac": [800.0], "actual_cost": [300.0], "revenue_recognised": [400.0], "loss_provision": [0.0]})
    with pytest.raises(FrameError, match=r"finance\.project_financials frame lacks column\(s\) period"):
        fin.margin_trail(pf, "PRJ-1", context=M3)
    out = fin.margin_trail(pf.assign(period="2026-02"), "PRJ-1", context=M3)
    assert out["margin_pct"].tolist() == [25.0]     # revenue 400, cost 300: (400 - 300) / 400


# statements_check: amount, prior_year_amount (text) and the footing mapping; a notes row is not read as numbers

def _sl(**over):
    return pd.DataFrame({"rpt_key": ["R-1", "R-1"], "statement": ["balance_sheet"] * 2, "line_no": [1, 2], "line_code": ["TA", "TEL"], "amount": [100.0, 100.0], "prior_year_amount": [None, None], "line_type": ["total"] * 2}).assign(**over)


def test_statements_check_valid_frame_is_clean():
    assert fin.statements_check(_sl(), context=M12).empty


def test_statements_check_text_prior_year_amount_names_the_column():
    with pytest.raises(FrameError, match=r"finance-reporting\.statement_line\.prior_year_amount must hold numbers, not 'abc'"):
        fin.statements_check(_sl(prior_year_amount=[1.0, "abc"]), context=M12)


def test_statements_check_text_amount_names_the_column():
    with pytest.raises(FrameError, match=r"finance-reporting\.statement_line\.amount must hold numbers, not 'abc'"):
        fin.statements_check(_sl(amount=[100.0, "abc"]), context=M12)


def test_statements_check_null_amount_is_a_null():
    with pytest.raises(FrameError, match=r"finance-reporting\.statement_line\.amount has a null; it must hold numbers"):
        fin.statements_check(_sl(amount=pd.Series([100.0, pd.NA], dtype=object)), context=M12)


def test_statements_check_a_notes_row_with_text_amounts_is_not_checked():
    notes = pd.DataFrame({"rpt_key": ["R-1"], "statement": ["notes"], "line_no": [3], "line_code": ["N1"], "amount": ["see note"], "prior_year_amount": ["n/a"], "line_type": ["text"]})
    assert fin.statements_check(pd.concat([_sl(), notes], ignore_index=True), context=M12).empty


# prior_year_column: codes holds text

def _py(codes):
    rep = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "le_key": ["LE-A", "LE-A"], "scope": ["entity", "entity"], "fiscal_year": [2024, 2025]})
    sl = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "statement": ["income_statement"] * 2, "line_code": ["REV", "REV"], "amount": [100.0, 120.0], "prior_year_amount": [None, 100.0]})
    return fin.prior_year_column(sl, rep, codes=codes, context=M12)


def test_prior_year_column_valid_codes_still_work():
    assert _py(("REV",)).empty
    assert _py(["REV"]).empty


@pytest.mark.parametrize("codes, shown", [([1, 2], "(1, 2)"), (("REV", 1), "('REV', 1)")])
def test_prior_year_column_codes_that_are_not_text_name_the_codes(codes, shown):
    with pytest.raises(FrameError, match=r"^codes must be a sequence of line codes \(text\), not " + shown.replace("(", r"\(").replace(")", r"\)")):
        _py(codes)
