"""Statutory statements: the lines rebuilt from the trial balance, the checks of a statement set, the prior year column, the filing status and the size criteria.

The statement lines of finance-reporting hold amounts in the currency of the report with the natural sign: revenue and liabilities positive, costs negative. Notes text and wording of any kind is not
provided here. Footing rules are a table of the line codes of the estate (PROPOSED, read from the nine reports).
"""
from __future__ import annotations

from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, fact, make_envelope, violations

from ._guard import staged
from ._util import _days, _need, _numeric, _round_half_away

_FOOTING = {
    "GP": ("REV", "OOI", "COS", "EXT"), "EBIT": ("GP", "STAFF", "DEP", "OOE"), "PBT": ("EBIT", "DIV", "FININC", "FINEXP"), "NI": ("PBT", "TAX"),
    "FA_TOT": ("FA_TANG", "FA_INV", "GRPLOAN", "DTA"), "CA_TOT": ("INVT", "CONTR_A", "TRADE_R", "OTH_R", "GRP_R", "PREP", "CASH"), "TA": ("FA_TOT", "CA_TOT"),
    "EQ_TOT": ("EQ_SC", "EQ_RE", "EQ_BF", "EQ_YR"), "PROV_TOT": ("PROV",), "LT_TOT": ("DEBT_GRP_LT",), "CL_TOT": ("TRADE_P", "CONTR_L", "GRP_P", "TAX_P", "OTH_P"), "LIAB_TOT": ("LT_TOT", "CL_TOT"),
    "TEL": ("EQ_TOT", "PROV_TOT", "LIAB_TOT"),
    "CF_OPS": ("CF_EBIT", "CF_DEP", "CF_GAIN", "CF_PROV", "CF_INVT", "CF_CONTR", "CF_TRADE_R", "CF_OTH_R", "CF_GRP", "CF_TRADE_P", "CF_OTH_P"),
    "CF_OPA": ("CF_OPS", "CF_FININC", "CF_FINEXP", "CF_DIV"), "CF_INVA": ("CF_CAPEX_T", "CF_PROCEEDS"), "CF_FINA": ("CF_EQ",), "CF_NET": ("CF_OPA", "CF_INVA", "CF_FINA"), "CF_CLOSE": ("CF_NET", "CF_OPEN"),
    "OPEN_TOT": ("OPEN_SC", "OPEN_RE"), "DIVPAID_TOT": ("DIVPAID_SC", "DIVPAID_RE"), "RESULT_TOT": ("RESULT_SC", "RESULT_RE"), "CLOSE_TOT": ("CLOSE_SC", "CLOSE_RE"),
}
_LINKS = (("TA", "TEL", "balance_sheet_balances"), ("CF_CLOSE", "CASH", "cash_flow_ends_at_cash"), ("CLOSE_TOT", "EQ_TOT", "equity_ends_at_balance_sheet"), ("RESULT_TOT", "NI", "equity_result_is_net_income"))
_SL = ("rpt_key", "statement", "line_no", "line_code", "amount", "prior_year_amount", "line_type")
_FREP_DK = "frep.annual_reports.DK"


def _cents(x: pd.Series) -> np.ndarray:
    """Integer cents of an amount column, half a cent away from zero (the float noise of x * 100 is cut at six decimals first); a null amount raises."""
    v = pd.to_numeric(x).to_numpy(dtype=float, na_value=np.nan)
    if np.isnan(v).any():
        raise FrameError(f"{int(np.isnan(v).sum())} amounts are null")
    if (~np.isfinite(v)).any() or (np.abs(v) >= 9e15).any():
        raise FrameError("amounts must be finite and below 9e15")
    return _round_half_away(np.round(v * 100, 6)).astype(np.int64)


class LedgerStatement(NamedTuple):
    """lines: map_code, line_code, statement, amount, n_accounts; unmapped: accounts with a balance and no statutory map; pbt: the sum of the income statement lines other than tax."""
    lines: pd.DataFrame
    unmapped: pd.DataFrame
    pbt: float


@staged(sources=("finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.debit", "finance.trial_balance.credit",
                 "finance.trial_balance.closing_balance", "finance.gl_account.gl_key", "finance.gl_account.statement", "finance.gl_account.dk_statutory_map", "finance.gl_account.de_statutory_map",
                 "finance.statutory_map_line.map_code", "finance.statutory_map_line.line_code", "finance.statutory_map_line.normal_side", "finance-reporting.statement_line.amount"),
        oracle="py:tests/test_finance_reporting.py::test_statements_tie_to_the_ledger")
def statement_from_ledger(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame, le_key: str, country: str, fiscal_year: int, *, require_full_year: bool = True) -> LedgerStatement:
    """Use this when you rebuild the statutory lines of one entity and fiscal year from its trial balance, in the entity currency and the natural sign.

    Rule: an income statement line is the movement of the year (credit less debit over the periods of the year) of the accounts mapped to it; a balance sheet line is the closing balance of the last period of the year, with the sign of the normal side of the line (credit positive). Amounts are summed in integer cents and returned in currency units (cents divided by 100, floats). In unmapped, amount_debit_positive_for_bs is credit less debit for income statement accounts and the debit positive closing balance for balance sheet accounts. The fiscal year is the calendar year. Accounts with a balance and no statutory map are returned in unmapped, and pbt is the sum of the income statement lines other than TAX; tax lines are not in the ledger accounts, so they appear as unmapped when an account carries them.

    Args:
        trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-03), gl_key, debit, credit and closing_balance, one row per entity, period and account.
        gl_account: Frame finance.gl_account with gl_key, statement (IS or BS) and the map column of the country (dk_statutory_map or de_statutory_map).
        statutory_map_line: Frame finance.statutory_map_line with map_code, line_code, statement and normal_side (debit or credit), one row per map code.
        le_key: The entity.
        country: DK or DE; it selects the map column of the chart of accounts.
        fiscal_year: The calendar year, a whole number.
        require_full_year: True demands all twelve periods of the year in the trial balance; False accepts a part year. Default True.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        LedgerStatement, a named tuple: lines (a DataFrame with map_code, line_code, statement, amount and n_accounts), unmapped (a DataFrame with gl_key, kind and amount_debit_positive_for_bs) and pbt (a number).

    Raises:
        FrameError: country is not DK or DE, fiscal_year is not a whole year, a column is missing, a key is repeated, an amount is null or text that is not a number, a period is null or malformed, a normal side is not debit or credit, an account is not in the chart of accounts, a statement is not IS or BS, the entity has no rows in the year or too few periods when require_full_year is true, a balance sheet account with a balance has no row in the last period, a map code is not in the map, or an account is mapped to a line of the other statement.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import statement_from_ledger
        >>> ctx = Context(stage="month12", role="analyst")
        >>> tb = pd.DataFrame({"le_key": ["LE-A", "LE-A"], "period": ["2026-01", "2026-01"], "gl_key": ["GL-4000", "GL-1000"], "debit": [0.0, 500.0], "credit": [500.0, 0.0], "closing_balance": [-500.0, 500.0]})
        >>> gl = pd.DataFrame({"gl_key": ["GL-4000", "GL-1000"], "statement": ["IS", "BS"], "dk_statutory_map": ["M-REV", "M-CASH"]})
        >>> ml = pd.DataFrame({"map_code": ["M-REV", "M-CASH"], "line_code": ["REV", "CASH"], "statement": ["IS", "BS"], "normal_side": ["credit", "debit"]})
        >>> res = statement_from_ledger(tb, gl, ml, "LE-A", "DK", 2026, require_full_year=False, context=ctx)
        >>> res.lines[["line_code", "statement", "amount"]].values.tolist()
        [['CASH', 'balance_sheet', 500.0], ['REV', 'income_statement', 500.0]]
        >>> res.pbt
        500.0
    """
    col = {"DK": "dk_statutory_map", "DE": "de_statutory_map"}.get(country)
    if col is None:
        raise FrameError(f"country must be DK or DE, not {country!r}")
    if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, (int, np.integer)):
        raise FrameError(f"fiscal_year must be a whole year, not {fiscal_year!r}")
    _need(trial_balance, ["le_key", "period", "gl_key", "debit", "credit", "closing_balance"], "finance.trial_balance")
    _need(gl_account, ["gl_key", "statement", col], "finance.gl_account")
    _need(statutory_map_line, ["map_code", "line_code", "statement", "normal_side"], "finance.statutory_map_line")
    if trial_balance.duplicated(["le_key", "period", "gl_key"]).any() or gl_account["gl_key"].duplicated().any() or statutory_map_line["map_code"].duplicated().any():
        raise FrameError("the trial balance, the chart of accounts and the map need unique keys")
    if trial_balance[["debit", "credit", "closing_balance"]].isna().any().any():
        raise FrameError("finance.trial_balance has null amounts")
    if trial_balance["period"].isna().any():
        raise FrameError("finance.trial_balance has rows without a period")
    sides = set(statutory_map_line["normal_side"].dropna().astype(str))
    if statutory_map_line["normal_side"].isna().any() or sides - {"debit", "credit"}:
        raise FrameError(f"finance.statutory_map_line.normal_side must be debit or credit in every row, not {sorted(sides - {'debit', 'credit'}) or ['null']}")
    gl = gl_account.assign(**{col: cast(Any, gl_account[col].astype(object)).where(gl_account[col].notna(), None), "statement": gl_account["statement"].astype(object)})
    t = trial_balance[(trial_balance["le_key"] == le_key) & (trial_balance["period"].astype(str).str[:4] == str(int(fiscal_year)))]
    if t.empty:
        raise FrameError(f"no trial balance rows of {le_key} in {int(fiscal_year)}")
    per = t["period"].astype(str)
    if not per.str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise FrameError(f"finance.trial_balance.period must be text like 2025-03, not {per[~per.str.fullmatch(r'\d{4}-(0[1-9]|1[0-2])')].iloc[0]!r}")
    if require_full_year and per.nunique() != 12:
        raise FrameError(f"{le_key} has {per.nunique()} periods in {int(fiscal_year)}, not twelve (require_full_year=False takes a part year)")
    _numeric(t, ["debit", "credit", "closing_balance"], "finance.trial_balance")
    try:
        t = t.assign(period=per.to_numpy()).merge(gl[["gl_key", "statement", col]], on="gl_key", how="left", validate="many_to_one")
    except (ValueError, TypeError) as e:
        raise FrameError(f"trial balance and chart of accounts do not join on gl_key: {e}") from None
    if t["statement"].isna().any():
        raise FrameError("trial balance accounts that are not in finance.gl_account")
    odd = sorted(set(t["statement"]) - {"IS", "BS"})
    if odd:
        raise FrameError(f"finance.gl_account.statement must be IS or BS, not {odd[0]!r}")
    last = t["period"].max()                                                      # periods are YYYY-MM text, so the text order is the time order
    bs = t[t["statement"] == "BS"]
    gone = bs[~bs["gl_key"].isin(bs.loc[bs["period"] == last, "gl_key"])].sort_values("period").groupby("gl_key").tail(1)       # the ledger omits an account from the month its balance is zero
    lost = sorted(gone.loc[_cents(gone["closing_balance"]) != 0, "gl_key"])
    if lost:
        raise FrameError(f"{len(lost)} balance sheet accounts end the year with a balance but have no row in the last period {last} (for example {lost[0]})")
    cents = lambda c: _cents(t[c])
    inc = t[t["statement"] == "IS"].assign(v=(cents("credit") - cents("debit"))[(t["statement"] == "IS").to_numpy()])
    bal = t[(t["statement"] == "BS") & (t["period"] == last)].assign(v=cents("closing_balance")[((t["statement"] == "BS") & (t["period"] == last)).to_numpy()])
    allv = pd.concat([inc.assign(kind="income_statement"), bal.assign(kind="balance_sheet")])
    un = allv[allv[col].isna()].groupby(["gl_key", "kind"], as_index=False)["v"].sum()
    un = un[un["v"].abs() > 0].assign(amount_debit_positive_for_bs=lambda d: d["v"] / 100.0).drop(columns="v")
    mapped = allv[allv[col].notna()]
    bad = sorted(set(mapped[col]) - set(statutory_map_line["map_code"]))
    if bad:
        raise FrameError(f"{len(bad)} map codes of the chart of accounts are not in finance.statutory_map_line (for example {bad[0]})")
    g = mapped.groupby([col, "kind"], as_index=False).agg(cents=("v", "sum"), n_accounts=("gl_key", "nunique")).rename(columns={col: "map_code", "kind": "statement"})
    g = g.merge(statutory_map_line[["map_code", "line_code", "normal_side", "statement"]].rename(columns={"statement": "map_statement"}), on="map_code", validate="many_to_one")
    wrong = g[g["map_statement"].astype(str).map({"IS": "income_statement", "BS": "balance_sheet"}) != g["statement"]]
    if len(wrong):
        raise FrameError(f"{len(wrong)} accounts are mapped to a line of the other statement (for example {wrong['map_code'].iloc[0]} is a {wrong['map_statement'].iloc[0]} line)")
    flip = (g["statement"] == "balance_sheet") & (g["normal_side"] == "credit")
    g["cents"] = np.where(flip, -g["cents"], g["cents"]).astype(np.int64)
    g["amount"] = g["cents"] / 100.0
    pbt = float(g.loc[(g["statement"] == "income_statement") & (g["line_code"] != "TAX"), "cents"].sum()) / 100.0
    return LedgerStatement(g[["map_code", "line_code", "statement", "amount", "n_accounts"]].sort_values(["statement", "map_code"]).reset_index(drop=True), un.reset_index(drop=True), pbt)


@staged(sources=tuple(f"finance-reporting.statement_line.{c}" for c in ("rpt_key", "statement", "line_no", "line_code", "amount", "prior_year_amount", "line_type")),
        oracle="py:tests/test_finance_reporting.py::test_balance_sheets_balance_and_cash_flow_reconciles")
def statements_check(statement_line: pd.DataFrame, *, tolerance: float = 0.011, link_tolerance: float = 0.005, footing: Mapping[str, Any] = _FOOTING) -> pd.DataFrame:
    """Use this when you check a set of statutory statements for lines that do not foot and links that do not hold, per report.

    Rule: foot (a subtotal or total equals the sum of its components in the footing table; components a report lacks count for nothing), balance_sheet_balances (TA equals TEL), cash_flow_ends_at_cash (CF_CLOSE equals CASH), equity_ends_at_balance_sheet (CLOSE_TOT equals EQ_TOT), equity_result_is_net_income (RESULT_TOT equals NI), equity_rolls (CLOSE_TOT equals OPEN_TOT plus DIVPAID_TOT plus RESULT_TOT, a missing DIVPAID_TOT counting as zero), cash_flow_opens_at_prior_cash (CF_OPEN equals the prior year CASH) and null_amount (a watched line with a null amount). Notes rows are skipped. For EBIT, when GP is missing or null, EBIT foots against REV, OOI, COS, EXT, STAFF, DEP and OOE (the German layout). The tolerances and the footing table are proposed business choices.

    Args:
        statement_line: Frame finance-reporting.statement_line with rpt_key, statement, line_no, line_code, amount, prior_year_amount and line_type, one row per report and line code.
        tolerance: Largest accepted difference when a line foots, zero or more. Default 0.011 (proposed).
        link_tolerance: Largest accepted difference for the links, the equity roll and the opening cash, zero or more. Default 0.005 (proposed).
        footing: Mapping from a subtotal line code to the tuple of its component codes. Default the footing table of the nine reports (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail; the key is the report key and the line code, and the frame is empty when every check holds.

    Raises:
        FrameError: a column is missing, tolerance or link_tolerance is not a number of zero or more, footing is not a mapping, amount or prior_year_amount holds text that is not a number, a row has no rpt_key, or a report has more than one row for a line code.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import statements_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> sl = pd.DataFrame({"rpt_key": ["R-1", "R-1"], "statement": ["balance_sheet"] * 2, "line_no": [1, 2], "line_code": ["TA", "TEL"], "amount": [100.0, 90.0], "prior_year_amount": [None, None], "line_type": ["total"] * 2})
        >>> statements_check(sl, context=ctx)[["key", "rule", "detail"]].values.tolist()
        [['R-1 TA', 'balance_sheet_balances', 'TA 100.00 against TEL 90.00']]
        >>> statements_check(sl.assign(amount=[100.0, 100.0]), context=ctx).empty
        True
    """
    _need(statement_line, list(_SL), "finance-reporting.statement_line")
    for name, v in (("tolerance", tolerance), ("link_tolerance", link_tolerance)):
        if not isinstance(v, (int, float, np.number)) or isinstance(v, bool) or not np.isfinite(v) or v < 0:
            raise FrameError(f"{name} must be zero or more")
    if not isinstance(footing, Mapping):
        raise FrameError(f"footing must be a mapping from a line code to the tuple of its component codes, not {footing!r}")
    body = statement_line[statement_line["statement"] != "notes"]
    _numeric(body, ["amount", "prior_year_amount"], "finance-reporting.statement_line", allow_null=["prior_year_amount"])
    if body["rpt_key"].isna().any():
        raise FrameError("finance-reporting.statement_line has rows without an rpt_key")
    if body.duplicated(["rpt_key", "statement", "line_code"]).any() or body.duplicated(["rpt_key", "line_code"]).any():
        raise FrameError("finance-reporting.statement_line has more than one row for a report and line code")
    watched = set(footing) | {c for comps in footing.values() for c in comps} | {c for a, b, _ in _LINKS for c in (a, b)} | {"CF_OPEN", "OPEN_TOT", "DIVPAID_TOT", "RESULT_TOT", "CLOSE_TOT"}
    rows = []
    add = lambda key, rule, detail: rows.append(("finance-reporting.statement_line", key, rule, detail))
    for rk, r in body.groupby("rpt_key", sort=True):
        amt = r.set_index("line_code")["amount"].astype(float)
        prior = r.set_index("line_code")["prior_year_amount"].astype(float)
        for code in sorted(c for c in amt.index[amt.isna()] if c in watched):
            add(f"{rk} {code}", "null_amount", f"the line {code} has no amount")
        for target, comps in footing.items():
            if target not in amt.index or pd.isna(amt[target]):
                continue
            if target == "EBIT" and ("GP" not in amt.index or pd.isna(amt["GP"])):
                comps = ("REV", "OOI", "COS", "EXT", "STAFF", "DEP", "OOE")          # the German layout has no gross profit line
            have = [c for c in comps if c in amt.index and pd.notna(amt[c])]
            if have and abs(float(amt[have].sum()) - float(amt[target])) > tolerance:
                add(f"{rk} {target}", "foot", f"{target} is {amt[target]:.2f}, its components {', '.join(have)} sum to {amt[have].sum():.2f}")
        for a, b, rule in _LINKS:
            if a in amt.index and b in amt.index and pd.notna(amt[a]) and pd.notna(amt[b]) and abs(float(amt[a]) - float(amt[b])) > link_tolerance:
                add(f"{rk} {a}", rule, f"{a} {amt[a]:.2f} against {b} {amt[b]:.2f}")
        roll = ["CLOSE_TOT", "OPEN_TOT", "RESULT_TOT"]                   # a report without dividend lines paid none
        div = float(amt["DIVPAID_TOT"]) if "DIVPAID_TOT" in amt.index and pd.notna(amt["DIVPAID_TOT"]) else 0.0
        if set(roll) <= set(amt.index) and amt[roll].notna().all() and abs(amt["OPEN_TOT"] + div + amt["RESULT_TOT"] - amt["CLOSE_TOT"]) > link_tolerance:
            add(f"{rk} CLOSE_TOT", "equity_rolls", "closing equity is not opening plus dividends plus result")
        if "CF_OPEN" in amt.index and pd.notna(amt["CF_OPEN"]) and "CASH" in prior.index and pd.notna(prior["CASH"]) and abs(float(amt["CF_OPEN"]) - float(prior["CASH"])) > link_tolerance:
            add(f"{rk} CF_OPEN", "cash_flow_opens_at_prior_cash", f"CF_OPEN {amt['CF_OPEN']:.2f} against the prior year cash {prior['CASH']:.2f}")
    return violations.frame(rows)


@staged(sources=(*(f"finance-reporting.statement_line.{c}" for c in ("rpt_key", "line_code", "amount", "prior_year_amount", "statement")), "finance-reporting.statutory_report.rpt_key", "finance-reporting.statutory_report.le_key",
                 "finance-reporting.statutory_report.scope", "finance-reporting.statutory_report.fiscal_year"), oracle="py:tests/test_finance_reporting.py::test_prior_year_column_is_previous_year")
def prior_year_column(statement_line: pd.DataFrame, statutory_report: pd.DataFrame, *, codes: Sequence[str] = ("REV", "NI", "TA", "EQ_TOT", "CF_CLOSE"), tolerance: float = 0.005) -> pd.DataFrame:
    """Use this when you check that the prior year column of each report equals the amount of the report of the year before.

    Rule: for each report whose entity (or group) has a report of the year before, prior_year_amount of the lines in codes must equal that report's amount within tolerance, else prior_year_differs; a missing prior amount, or a previous report with no line or no amount, is prior_year_missing. The first report of an entity must have a null prior on lines that are not balance sheet lines, else first_year_prior. A report after a gap in the years has no previous report and is not checked. The five default lines and the tolerance are proposed business choices.

    Args:
        statement_line: Frame finance-reporting.statement_line with rpt_key, statement, line_code, amount and prior_year_amount, one row per report and line code; notes rows are skipped.
        statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, scope and fiscal_year, one row per report; a group report has a null le_key.
        codes: The line codes to check, a sequence of text. Default REV, NI, TA, EQ_TOT and CF_CLOSE (proposed).
        tolerance: Largest accepted difference, zero or more. Default 0.005 (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail; the key is the report key and the line code, and the frame is empty when every prior year amount agrees.

    Raises:
        FrameError: a column is missing, codes is not a sequence of text, tolerance is not a number of zero or more, an rpt_key or a report line is repeated, fiscal_year is not a whole year in every row, or two reports have the same entity and fiscal year.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import prior_year_column
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rep = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "le_key": ["LE-A", "LE-A"], "scope": ["entity", "entity"], "fiscal_year": [2024, 2025]})
        >>> sl = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "statement": ["income_statement"] * 2, "line_code": ["REV", "REV"], "amount": [100.0, 120.0], "prior_year_amount": [None, 90.0]})
        >>> prior_year_column(sl, rep, codes=("REV",), context=ctx)[["key", "rule", "detail"]].values.tolist()
        [['R-25 REV', 'prior_year_differs', 'prior 90.00, the report R-24 has 100.00']]
        >>> prior_year_column(sl.assign(prior_year_amount=[None, 100.0]), rep, codes=("REV",), context=ctx).empty
        True
    """
    _need(statement_line, ["rpt_key", "statement", "line_code", "amount", "prior_year_amount"], "finance-reporting.statement_line")
    _need(statutory_report, ["rpt_key", "le_key", "scope", "fiscal_year"], "finance-reporting.statutory_report")
    if isinstance(codes, str):
        raise FrameError(f"codes is a sequence of line codes, not a string ({codes!r})")
    if not hasattr(codes, "__iter__"):
        raise FrameError(f"codes must be a sequence of line codes, not {type(codes).__name__} ({codes!r})")
    codes = tuple(codes)
    if not all(isinstance(c, str) for c in codes):
        raise FrameError(f"codes must be a sequence of line codes (text), not {codes!r}")
    if not isinstance(tolerance, (int, float, np.number)) or isinstance(tolerance, bool) or not np.isfinite(tolerance) or tolerance < 0:
        raise FrameError("tolerance must be zero or more")
    if statutory_report["rpt_key"].duplicated().any():
        raise FrameError("finance-reporting.statutory_report has more than one row for an rpt_key")
    fy = statutory_report["fiscal_year"]
    if fy.isna().any() or not pd.api.types.is_integer_dtype(fy) and not (pd.api.types.is_float_dtype(fy) and (fy % 1 == 0).all()):
        raise FrameError("finance-reporting.statutory_report.fiscal_year must be a whole year in every row")
    rep = statutory_report.assign(fiscal_year=fy.astype("int64"), who=statutory_report["scope"].astype(str) + ":" + statutory_report["le_key"].astype(object).where(statutory_report["le_key"].notna(), "-").astype(str))
    if rep.duplicated(["who", "fiscal_year"]).any():
        raise FrameError("two reports of the same entity and fiscal year")
    cur = rep.set_index(["who", "fiscal_year"])["rpt_key"]
    first = rep.groupby("who")["fiscal_year"].min()
    body = statement_line[statement_line["statement"] != "notes"]
    if body.duplicated(["rpt_key", "line_code"]).any():
        raise FrameError("finance-reporting.statement_line has more than one row for a report and line code")
    sl = body.set_index(["rpt_key", "line_code"])
    rows = []
    add = lambda key, rule, detail: rows.append(("finance-reporting.statement_line", key, rule, detail))
    r: Any
    for r in rep.sort_values(["who", "fiscal_year"]).itertuples():
        before = cur.get((r.who, r.fiscal_year - 1))
        if before is None and r.fiscal_year > first[r.who]:
            continue                                                              # a gap in the years: no previous report to compare with
        for c in codes:
            if (r.rpt_key, c) not in sl.index:
                continue
            cell: Any = sl.loc[(r.rpt_key, c)]
            stmt, prior = cell["statement"], cell["prior_year_amount"]
            if before is None:
                if stmt != "balance_sheet" and pd.notna(prior):
                    add(f"{r.rpt_key} {c}", "first_year_prior", f"the first report has a prior year amount {float(prior):.2f}")
            elif (before, c) not in sl.index:
                add(f"{r.rpt_key} {c}", "prior_year_missing", f"the report {before} has no line {c}")
            elif pd.isna(sl.loc[(before, c), "amount"]):
                add(f"{r.rpt_key} {c}", "prior_year_missing", f"the report {before} has no amount on the line {c}")
            elif pd.isna(prior):
                add(f"{r.rpt_key} {c}", "prior_year_missing", f"no prior year amount, the report {before} has {float(sl.loc[(before, c), 'amount']):.2f}")
            elif abs(float(prior) - float(sl.loc[(before, c), "amount"])) > tolerance:
                add(f"{r.rpt_key} {c}", "prior_year_differs", f"prior {float(prior):.2f}, the report {before} has {float(sl.loc[(before, c), 'amount']):.2f}")
    return violations.frame(rows)


def _dk_mask(le_key: pd.Series, dk_entities: Any) -> np.ndarray:
    """True for the reports of the entities in dk_entities (None stands for the group, a null le_key); a string instead of a sequence raises."""
    if isinstance(dk_entities, str) or not hasattr(dk_entities, "__iter__"):
        raise FrameError("dk_entities is a sequence of le_key values (None for the group), not a string")
    keys = set(dk_entities)
    k = le_key.astype(object)
    hit = k.isin([x for x in keys if x is not None]).to_numpy(dtype=bool)
    return hit | (k.isna().to_numpy(dtype=bool) & (None in keys))


@staged(sources=("finance-reporting.statutory_report.rpt_key", "finance-reporting.statutory_report.period_end", "finance-reporting.statutory_report.filing_deadline", "finance-reporting.statutory_report.filed_date",
                 "finance-reporting.statutory_report.le_key", "finance-reporting.statutory_report.filed_on_time"), facts=(f"{_FREP_DK}.filing_deadline_months_after_year_end",),
        oracle="py:tests/test_finance_reporting.py::test_report_order_and_dates")
def filing_status(statutory_report: pd.DataFrame, *, dk_entities: Sequence[str | None] = ("LE-01", None)) -> Envelope:
    """Use this when you need to know whether each annual report was filed on time, from the deadline and the filed date.

    Rule: the status comes from the stored deadline: on_time when filed on or before it (whatever the time of day), late after it, not_filed without a filed date, no_deadline without a deadline. The Danish deadline rule (the fact frep.annual_reports.DK.filing_deadline_months_after_year_end, VERIFY) only checks the stored one; German entities are not checked. The envelope carries the VERIFY status.

    Args:
        statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, period_end, filing_deadline, filed_date and filed_on_time, one row per report.
        dk_entities: The entities judged by the Danish rule, the group as None. Default LE-01 and the group (PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value has rpt_key, le_key, period_end, deadline_stored, deadline_rule, rule_agrees, filed_date, days_late (negative when early), status and filed_on_time_agrees.

    Raises:
        FrameError: a column is missing or a report key is repeated.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import filing_status
        >>> ctx = Context(stage="month12", role="analyst")
        >>> reports = pd.DataFrame({"rpt_key": ["R1", "R2"], "le_key": ["LE-01", "LE-02"], "period_end": ["2025-12-31"] * 2, "filing_deadline": ["2026-05-31"] * 2,
        ...                         "filed_date": ["2026-05-20", None], "filed_on_time": [True, False]})
        >>> filing_status(reports, context=ctx).value[["rpt_key", "status"]].values.tolist()
        [['R1', 'on_time'], ['R2', 'not_filed']]
    """
    _need(statutory_report, ["rpt_key", "le_key", "period_end", "filing_deadline", "filed_date", "filed_on_time"], "finance-reporting.statutory_report")
    if statutory_report["rpt_key"].duplicated().any():
        raise FrameError("finance-reporting.statutory_report has more than one row for an rpt_key")
    f = fact(f"{_FREP_DK}.filing_deadline_months_after_year_end")
    months = int(f.value)
    d = _days(statutory_report, ["period_end", "filing_deadline", "filed_date"], "finance-reporting.statutory_report")
    pe, dl, fd = d["period_end"], d["filing_deadline"], d["filed_date"]
    rule = pe + pd.DateOffset(months=months)
    rule = rule.where(~pe.dt.is_month_end.fillna(False), rule + pd.offsets.MonthEnd(0))
    is_dk = _dk_mask(statutory_report["le_key"], dk_entities)
    out = pd.DataFrame({"rpt_key": statutory_report["rpt_key"], "le_key": statutory_report["le_key"], "period_end": pe, "deadline_stored": dl, "deadline_rule": rule.where(is_dk), "filed_date": fd})
    agree = pd.Series(pd.array([pd.NA] * len(out), dtype="boolean"), index=out.index)
    judged = is_dk & pe.notna().to_numpy() & dl.notna().to_numpy()
    agree[judged] = (rule == dl)[judged].to_numpy()
    out["rule_agrees"] = agree
    out["days_late"] = (fd - dl).dt.days.astype("Int64")
    out["status"] = np.where(fd.isna(), "not_filed", np.where(dl.isna(), "no_deadline", np.where(fd <= dl, "on_time", "late")))
    stored = statutory_report["filed_on_time"].astype("boolean").reset_index(drop=True)
    agrees = pd.Series(pd.array(cast(Any, (stored == pd.Series(out["status"].to_numpy() == "on_time"))).to_numpy(dtype=object, na_value=pd.NA), dtype="boolean"))
    nf = (out["status"] == "not_filed").to_numpy()
    agrees[nf] = stored.isna().to_numpy()[nf]
    agrees[(out["status"] == "no_deadline").to_numpy()] = pd.NA                      # nothing to compare the flag with
    out["filed_on_time_agrees"] = agrees.array
    return make_envelope(out.reset_index(drop=True), "halvaro.finance.statements.filing_status", facts=[f], sources=("finance-reporting.statutory_report",))


@staged(sources=tuple(f"finance-reporting.statutory_report.{c}" for c in ("rpt_key", "le_key", "revenue", "total_assets", "average_employees", "size_criteria_met")),
        facts=(f"{_FREP_DK}.size_thresholds.net_revenue", f"{_FREP_DK}.size_thresholds.balance_sheet_total", f"{_FREP_DK}.size_thresholds.average_full_time_employees"), oracle="py:tests/test_statements.py::test_size_class_edges_envelope_and_group_keys")
def size_class(statutory_report: pd.DataFrame, *, dk_entities: Sequence[str | None] = ("LE-01", None)) -> Envelope:
    """Use this when you need how many of the three Danish size criteria a report exceeds: revenue, balance sheet total and average employees.

    Rule: each value is compared with the threshold of its fact (all VERIFY, the envelope carries that status); a value above the threshold exceeds it, a value at the threshold does not. Only the entities in dk_entities are judged; the others are listed with empty criteria (no German thresholds are a fact). The reporting class is not derived here.

    Args:
        statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, revenue, total_assets, average_employees and size_criteria_met.
        dk_entities: The entities judged, the group as None. Default LE-01 and the group (PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value has rpt_key, le_key, revenue_over, assets_over, employees_over, criteria_exceeded, size_criteria_met (stored) and agrees (empty when the stored count is empty).

    Raises:
        FrameError: a column is missing, or a judged report has no number in revenue, total assets or employees.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import size_class
        >>> ctx = Context(stage="month12", role="analyst")
        >>> reports = pd.DataFrame({"rpt_key": ["R1", "R2"], "le_key": ["LE-01"] * 2, "revenue": [0, 10 ** 13], "total_assets": [0, 10 ** 13], "average_employees": [0, 10 ** 6], "size_criteria_met": [0, 3]})
        >>> size_class(reports, context=ctx).value[["rpt_key", "criteria_exceeded", "agrees"]].values.tolist()
        [['R1', 0.0, True], ['R2', 3.0, True]]
    """
    _need(statutory_report, ["rpt_key", "le_key", "revenue", "total_assets", "average_employees", "size_criteria_met"], "finance-reporting.statutory_report")
    dk = _dk_mask(statutory_report["le_key"], dk_entities)
    if statutory_report.loc[dk, ["revenue", "total_assets", "average_employees"]].isna().any().any():
        raise FrameError("finance-reporting.statutory_report has null revenue, total assets or employees on a judged report")
    facts = [fact(f"{_FREP_DK}.size_thresholds.{k}") for k in ("net_revenue", "balance_sheet_total", "average_full_time_employees")]
    rev, ta, emp = (f.value for f in facts)
    def num(c: str) -> np.ndarray:
        col = statutory_report[c]
        if any(isinstance(v, (bool, np.bool_, str)) for v in col[dk].dropna()):
            raise FrameError(f"finance-reporting.statutory_report.{c} must hold numbers on a judged report")
        return pd.to_numeric(col, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    over = {"revenue_over": num("revenue") > rev, "assets_over": num("total_assets") > ta, "employees_over": num("average_employees") > emp}
    o = pd.DataFrame({"rpt_key": statutory_report["rpt_key"], "le_key": statutory_report["le_key"]})
    for k, v in over.items():
        o[k] = cast(Any, pd.Series(pd.array(np.where(dk, v, False), dtype="boolean"), index=o.index)).where(dk, pd.NA)
    n = sum(v.astype(int) for v in over.values())
    o["criteria_exceeded"] = np.where(dk, n, np.nan)
    stored = pd.to_numeric(statutory_report["size_criteria_met"], errors="coerce")
    o["size_criteria_met"] = stored.to_numpy()
    ag = pd.Series(pd.array([pd.NA] * len(o), dtype="boolean"), index=o.index)
    j = dk & stored.notna().to_numpy()
    ag[j] = (n == stored.to_numpy())[j]
    o["agrees"] = ag
    return make_envelope(o.reset_index(drop=True), "halvaro.finance.statements.size_class", facts=facts, sources=("finance-reporting.statutory_report",))
