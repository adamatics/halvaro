"""Payroll checks (plan 5.5): gross pay from the ledger, the tie-out against the hr aggregate, employer on-costs, labour absorption and the cost centre to team map.

No function here returns pay per person. The hr side arrives as an aggregate frame (halvaro.hr.payroll_aggregate) and a frame with an employee key or a base salary column is refused. The tie-out
is an internal consistency check, not an audit: the stored reconciliation is built from the same employment terms (plan 5.5, risk row).
"""
from __future__ import annotations

import numbers
from decimal import Decimal
from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, fact, make_envelope, violations

from ._guard import staged
from ._util import _cents, _need, _numeric
from .vat_tax import _tol_cents

_GROSS = ("GL-7000", "GL-7005", "GL-7050")           # PROPOSED (fact needed: fin.payroll_on_costs.gross_salary_accounts): salaries, management salaries, apprentices and interns
_TOLERANCE = "policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk"
_RATES = {"pension": "fin.payroll_on_costs.{c}.employer_pension_share", "social": "fin.payroll_on_costs.{c}.employer_social_share"}
_FORBIDDEN = ("emp_key", "base_salary", "employee_key", "hr.employment_term.base_salary")


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.cc_key", "finance.journal_line.gl_key", "finance.journal_line.period", "finance.journal_line.amount"),
        oracle="py:tests/test_finance_planning.py::test_payroll_summary_components_tie_to_the_ledger")
def ledger_gross_pay(journal_line: pd.DataFrame, *, accounts: tuple[str, ...] = _GROSS) -> pd.DataFrame:
    """Use this when you need the gross salary booked in the ledger per legal entity, cost centre and month, to tie out against the payroll summary.

    Rule: the sum of the journal lines on the salary accounts, in the currency of the entity, debit positive, to the cent. The default accounts GL-7000, GL-7005 and GL-7050 are PROPOSED until fin.payroll_on_costs.gross_salary_accounts is a fact.

    Args:
        journal_line: Frame finance.journal_line with le_key, cc_key, gl_key, period and amount.
        accounts: The salary accounts (default GL-7000, GL-7005 and GL-7050, PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with le_key, cc_key, period and ledger_gross_pay, sorted by those three columns.

    Raises:
        FrameError: a column is missing, accounts is not a non-empty tuple of account keys, or a line on these accounts has no cost centre, entity or period.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import ledger_gross_pay
        >>> ctx = Context(stage="month3", role="analyst")
        >>> lines = pd.DataFrame({"le_key": ["LE-01"] * 3, "cc_key": ["CC-1"] * 3, "gl_key": ["GL-7000", "GL-7005", "GL-6000"], "period": ["2026-03"] * 3, "amount": [1000.5, 200.25, 50.0]})
        >>> ledger_gross_pay(lines, context=ctx).to_dict("records")
        [{'le_key': 'LE-01', 'cc_key': 'CC-1', 'period': '2026-03', 'ledger_gross_pay': 1200.75}]
        >>> ledger_gross_pay(lines.assign(cc_key=[None, "CC-1", "CC-1"]), context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: gross salary lines without a cost centre, entity or period; the tie-out is per cost centre
    """
    _need(journal_line, ["le_key", "cc_key", "gl_key", "period", "amount"], "finance.journal_line")
    if isinstance(accounts, str) or not accounts or not all(isinstance(a, str) for a in accounts):
        raise FrameError("accounts is a tuple of account keys")
    x = journal_line[journal_line["gl_key"].isin(list(accounts))]
    if x["cc_key"].isna().any() or x[["le_key", "period"]].isna().any().any():
        raise FrameError("gross salary lines without a cost centre, entity or period; the tie-out is per cost centre")
    c = pd.DataFrame({"le_key": x["le_key"].to_numpy(), "cc_key": x["cc_key"].to_numpy(), "period": x["period"].astype(str).to_numpy(), "c": _cents(x["amount"])})
    out: pd.DataFrame = cast(Any, c.groupby(["le_key", "cc_key", "period"], as_index=False, observed=True)["c"].sum())
    out["ledger_gross_pay"] = out.pop("c") / 100.0
    return out.sort_values(["le_key", "cc_key", "period"]).reset_index(drop=True)


_PERSON_WORDS = ("emp_key", "employee", "person_key", "salary", "monthly_pay", "base_pay")


def _individual(frame: pd.DataFrame) -> list[str]:
    """Columns or index names that look like a person or a person's pay (case-insensitive), except the aggregate pay column."""
    names = [str(c) for c in frame.columns] + [str(n) for n in frame.index.names if n is not None]
    return [n for n in names if n.lower() != "hr_gross_pay" and (n in _FORBIDDEN or any(w in n.lower() for w in _PERSON_WORDS))]


def _ccs(value: Any) -> list[str]:
    return [c.strip() for c in str(value).split(",") if c.strip()]


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.cc_key", "finance.payroll_hr_reconciliation.difference", "finance.payroll_hr_reconciliation.within_tolerance",
                 "finance.payroll_hr_reconciliation.within_band_envelope"), facts=(_TOLERANCE,),
        oracle="py:halvaro_gen/world/finance/checks.py::payroll_vs_hr")
def tie_out(ledger_gross: pd.DataFrame, hr_aggregate: pd.DataFrame, *, tolerance: float | None = None, band_floor_factor: float = 0.97, band_ceiling_factor: float = 1.02) -> Envelope:
    """Use this when you check the gross pay of the ledger against the aggregate of the hr side, per group of cost centres and month.

    Rule: the ledger gross pay of all cost centres of a group of the aggregate is compared with its hr gross pay; they are tied when the difference (ledger less hr) is within tolerance. The ledger must also sit between the band minimum total times band_floor_factor and the band maximum total times band_ceiling_factor. Status is tied, difference, outside_band, suppressed (the aggregate hides the row) or ledger_only (the ledger has a cost centre that no group holds). This is an internal consistency check, not an audit, and no pay per person is accepted.

    Args:
        ledger_gross: The result of ledger_gross_pay, with le_key, cc_key, period and ledger_gross_pay, one row per entity, cost centre and month.
        hr_aggregate: The result of halvaro.hr.payroll_aggregate with le_key, cc_key, period, currency, hr_gross_pay, band_minimum_total, band_maximum_total, cost_centres (comma separated) and suppressed.
        tolerance: Largest accepted difference per group and month. None takes the fact policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk (proposed). Optional.
        band_floor_factor: Factor on the band minimum total. Default 0.97 (proposed).
        band_ceiling_factor: Factor on the band maximum total. Default 1.02 (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, cc_key, period, cost_centres, currency, ledger_gross_pay, hr_gross_pay, difference, band_minimum_total, band_maximum_total, within_tolerance, within_band_envelope and status.

    Raises:
        FrameError: a column is missing, a frame has a column that names a person or a base salary, tolerance or a factor is not a valid number, a ledger or aggregate row is repeated, suppressed or cost_centres is null or not valid, an unsuppressed row has a null pay or band total, or a cost centre is in two groups of the same month.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import tie_out
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ledger = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "ledger_gross_pay": [1000.0]})
        >>> hr = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "currency": ["DKK"], "hr_gross_pay": [1000.0], "band_minimum_total": [900.0],
        ...                    "band_maximum_total": [1100.0], "cost_centres": ["CC-1"], "suppressed": [False]})
        >>> tie_out(ledger, hr, context=ctx).value[["cc_key", "difference", "status"]].values.tolist()
        [['CC-1', 0.0, 'tied']]
        >>> tie_out(ledger, hr.assign(hr_gross_pay=900.0), context=ctx).value["status"].tolist()
        ['difference']
    """
    _need(ledger_gross, ["le_key", "cc_key", "period", "ledger_gross_pay"], "ledger_gross_pay output")
    _need(hr_aggregate, ["le_key", "cc_key", "period", "currency", "hr_gross_pay", "band_minimum_total", "band_maximum_total", "cost_centres", "suppressed"], "hr payroll aggregate")
    bad = _individual(hr_aggregate) + _individual(ledger_gross)
    if bad:
        raise FrameError(f"the hr frame has individual columns ({', '.join(map(str, bad))}); pass the aggregate from halvaro.hr.payroll_aggregate, never pay per person")
    facts = []
    if tolerance is None:
        facts.append(fact(_TOLERANCE))
        tolerance = float(facts[0].value)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float, np.number)) or not np.isfinite(tolerance) or tolerance < 0:
        raise FrameError("tolerance must be zero or more")
    for name, v in (("band_floor_factor", band_floor_factor), ("band_ceiling_factor", band_ceiling_factor)):
        if isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not np.isfinite(v) or v <= 0:
            raise FrameError(f"{name} must be a positive number")
    if ledger_gross.duplicated(["le_key", "cc_key", "period"]).any():
        raise FrameError("the ledger frame has more than one row for an entity, cost centre and month")
    if hr_aggregate.duplicated(["le_key", "cc_key", "period", "currency"]).any():
        raise FrameError("the hr aggregate has more than one row for an entity, cost centre, month and currency")
    if hr_aggregate["suppressed"].isna().any() or not all(isinstance(v, (bool, np.bool_)) for v in hr_aggregate["suppressed"]):
        raise FrameError("hr payroll aggregate: suppressed must be true or false on every row")
    if hr_aggregate["cost_centres"].isna().any():
        raise FrameError("hr payroll aggregate: cost_centres is null on a row")
    if hr_aggregate.loc[~hr_aggregate["suppressed"].astype(bool), ["hr_gross_pay", "band_minimum_total", "band_maximum_total"]].isna().any().any():
        raise FrameError("hr payroll aggregate: an unsuppressed row has a null pay or band total")
    members = {}
    r: Any
    for r in hr_aggregate.itertuples():
        for cc in _ccs(r.cost_centres):
            if (r.le_key, cc, r.period) in members:
                raise FrameError(f"cost centre {cc} is in two groups of the aggregate in {r.period}")
            members[(r.le_key, cc, r.period)] = True
    led = ledger_gross.set_index(["le_key", "cc_key", "period"])["ledger_gross_pay"]
    rows: list[dict[str, Any]] = []
    for r in hr_aggregate.itertuples():
        keys = [(r.le_key, cc, r.period) for cc in _ccs(r.cost_centres)]
        lg = round(float(sum(led.get(k, 0.0) for k in keys)), 2)
        base = {"le_key": r.le_key, "cc_key": r.cc_key, "period": r.period, "cost_centres": r.cost_centres, "currency": r.currency, "ledger_gross_pay": lg}
        if bool(r.suppressed):
            rows.append({**base, "hr_gross_pay": np.nan, "difference": np.nan, "band_minimum_total": np.nan, "band_maximum_total": np.nan, "within_tolerance": pd.NA, "within_band_envelope": pd.NA, "status": "suppressed"})
            continue
        diff = round(lg - float(r.hr_gross_pay), 2)
        tied = abs(diff) <= tolerance + 1e-9
        band = float(r.band_minimum_total) * band_floor_factor <= lg <= float(r.band_maximum_total) * band_ceiling_factor
        rows.append({**base, "hr_gross_pay": float(r.hr_gross_pay), "difference": diff, "band_minimum_total": float(r.band_minimum_total), "band_maximum_total": float(r.band_maximum_total),
                     "within_tolerance": bool(tied), "within_band_envelope": bool(band), "status": "tied" if tied and band else ("difference" if not tied else "outside_band")})
    extra = ledger_gross[[(a, b, c) not in members for a, b, c in zip(ledger_gross["le_key"], ledger_gross["cc_key"], ledger_gross["period"])]]
    for r in extra.itertuples():
        if abs(r.ledger_gross_pay) > 0:
            rows.append({"le_key": r.le_key, "cc_key": r.cc_key, "period": r.period, "cost_centres": r.cc_key, "currency": None, "ledger_gross_pay": float(r.ledger_gross_pay), "hr_gross_pay": np.nan,
                         "difference": np.nan, "band_minimum_total": np.nan, "band_maximum_total": np.nan, "within_tolerance": False, "within_band_envelope": False, "status": "ledger_only"})
    cols = ["le_key", "cc_key", "period", "cost_centres", "currency", "ledger_gross_pay", "hr_gross_pay", "difference", "band_minimum_total", "band_maximum_total", "within_tolerance", "within_band_envelope", "status"]
    out = pd.DataFrame(rows, columns=cols).sort_values(["le_key", "cc_key", "period"]).reset_index(drop=True)
    return make_envelope(out, "halvaro.finance.payroll.tie_out", facts=facts, sources=("finance.journal_line", "hr.team"),
                         warnings=("internal consistency: the HR side is built from the same employment terms as the ledger, this is not an audit",))


@staged(sources=("finance.payroll_summary.le_key", "finance.payroll_summary.cc_key", "finance.payroll_summary.period", "finance.payroll_summary.component", "finance.payroll_summary.amount"),
        facts=tuple(v.format(c=c) for v in _RATES.values() for c in ("DK", "DE")), oracle="py:tests/test_finance_planning.py::test_payroll_summary_components_tie_to_the_ledger")
def employer_oncosts(gross: pd.DataFrame, *, country_of: dict[str, str], base: str = "gross_plus_overtime") -> Envelope:
    """Use this when you need the employer pension and social contributions on gross pay, per entity, cost centre and month, by country.

    Rule: each contribution is the share of its fact (fin.payroll_on_costs.<country>.employer_pension_share and employer_social_share, VERIFY) times the base amount, rounded to the cent with halves away from zero. The base_amount is rounded to two decimals with numpy round (halves to even). The base amount is the gross salary plus overtime (a null or missing overtime counts as zero), or the gross salary alone with base "gross". Holiday pay is not computed.

    Args:
        gross: Frame with le_key, cc_key, period and gross_salary, and optionally overtime, one row per entity, cost centre and month.
        country_of: Dict from every le_key of the frame to its country, DK or DE; it selects the two shares.
        base: "gross_plus_overtime" (gross salary plus overtime) or "gross" (gross salary only). Default "gross_plus_overtime".
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, cc_key, period, base_amount, employer_pension and employer_social, sorted by le_key, cc_key and period; the envelope carries the facts used and their VERIFY status.

    Raises:
        FrameError: a column is missing, gross_salary or overtime holds text that is not a number, gross_salary has a null, a row is repeated for an entity, cost centre and month, base is not one of the two names, or country_of is not a dict that maps every le_key of the frame to DK or DE.
        FactNotFound: a share fact is not in the fact set; the facts of both DK and DE are read, so a missing DE fact raises it even when every entity is Danish.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import employer_oncosts
        >>> ctx = Context(stage="month12", role="analyst")
        >>> gross = pd.DataFrame({"le_key": ["LE-A"], "cc_key": ["CC-1"], "period": ["2026-01"], "gross_salary": [1000.0], "overtime": [100.0]})
        >>> out = employer_oncosts(gross, country_of={"LE-A": "DK"}, context=ctx).value
        >>> out.columns.tolist()
        ['le_key', 'cc_key', 'period', 'base_amount', 'employer_pension', 'employer_social']
        >>> out["base_amount"].tolist()
        [1100.0]
        >>> employer_oncosts(gross, country_of={"LE-A": "DK"}, base="gross", context=ctx).value["base_amount"].tolist()
        [1000.0]
        >>> employer_oncosts(gross, country_of={"LE-A": "DK"}, base="net", context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: base is 'gross_plus_overtime' or 'gross'
    """
    _need(gross, ["le_key", "cc_key", "period", "gross_salary"], "gross pay frame")
    _numeric(gross, ["gross_salary"], "gross pay frame")
    if base == "gross_plus_overtime" and "overtime" in gross.columns:
        _numeric(gross, ["overtime"], "gross pay frame", allow_null=["overtime"])
    if gross["gross_salary"].isna().any():
        raise FrameError("gross pay frame: gross_salary has nulls")
    if gross.duplicated(["le_key", "cc_key", "period"]).any():
        raise FrameError("gross pay frame has more than one row for an entity, cost centre and month")
    if base not in ("gross_plus_overtime", "gross"):
        raise FrameError("base is 'gross_plus_overtime' or 'gross'")
    if not isinstance(country_of, dict) or not set(gross["le_key"]) <= set(country_of) or not set(country_of.values()) <= {"DK", "DE"}:
        raise FrameError("country_of maps every le_key of the frame to DK or DE")
    ot = gross["overtime"].fillna(0.0) if "overtime" in gross.columns else pd.Series(0.0, index=gross.index)
    amount = gross["gross_salary"].astype(float) + (ot.astype(float) if base == "gross_plus_overtime" else 0.0)
    f = {(c, k): fact(v.format(c=c)) for c in ("DK", "DE") for k, v in _RATES.items()}
    ctry = gross["le_key"].map(country_of)
    pen = np.array([float(f[(c, "pension")].value) for c in ctry])
    soc = np.array([float(f[(c, "social")].value) for c in ctry])
    used = [f[(c, k)] for c in sorted(set(ctry)) for k in _RATES]
    half_away = lambda v: np.sign(v) * np.floor(np.abs(v) * 100 + 0.5 + 1e-9) / 100
    out = pd.DataFrame({"le_key": gross["le_key"].to_numpy(), "cc_key": gross["cc_key"].to_numpy(), "period": gross["period"].to_numpy(), "base_amount": amount.round(2).to_numpy(),
                        "employer_pension": half_away(amount.to_numpy() * pen), "employer_social": half_away(amount.to_numpy() * soc)})
    return make_envelope(out.sort_values(["le_key", "cc_key", "period"]).reset_index(drop=True), "halvaro.finance.payroll.employer_oncosts", facts=used, sources=("finance.payroll_summary",))


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.gl_key", "finance.journal_line.period", "finance.journal_line.amount"),
        oracle="py:halvaro_gen/world/finance/checks.py::labour_absorption")
def labour_absorption_check(journal_line: pd.DataFrame, *, project_labour: str = "GL-6100", project_absorbed: str = "GL-7900", service_absorbed: str = "GL-7910",
                            service_accounts: tuple[str, ...] = ("GL-6610", "GL-6620"), max_warranty_share: float = 0.2, tolerance: float = 0.005) -> pd.DataFrame:
    """Use this when you check that labour booked on projects and on service is absorbed in the ledger, per entity and month for projects and over the whole window for service.

    Rule: for each entity and month, the lines on project_labour and project_absorbed must net to zero within tolerance, else the violation project_labour_not_absorbed. Over the whole window and all entities, the service labour (the lines on service_accounts) must be covered by the credit on service_absorbed, and the absorbed amount may exceed it by at most max_warranty_share of itself (the rest is the warranty ticket charge), else the violation service_labour_not_absorbed. The service sums use amount_dkk when the frame has it, otherwise amount. Amounts are in currency units and summed in whole cents; the tolerance is cut down to whole cents. All keyword defaults are proposed business choices (accounts, share and tolerance).

    Args:
        journal_line: Frame finance.journal_line with le_key, gl_key, period and amount, and optionally amount_dkk and currency, one row per line.
        project_labour: Account of project labour at standard rate. Default GL-6100 (proposed).
        project_absorbed: Account of labour absorbed to projects. Default GL-7900 (proposed).
        service_absorbed: Account of labour absorbed to service. Default GL-7910 (proposed).
        service_accounts: Accounts of service labour, as a tuple. Default GL-6610 and GL-6620 (proposed).
        max_warranty_share: Largest share of the absorbed service amount that may exceed the service labour, from 0 to below 1. Default 0.2 (proposed).
        tolerance: Largest accepted difference in currency units, zero or more. Default 0.005 (proposed).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail: project_labour_not_absorbed (key is the entity and month; the net amount is written in the detail text, not in a column) and service_labour_not_absorbed (key is "window"); empty when the labour is absorbed.

    Raises:
        FrameError: a column is missing, an amount is null, an le_key is null, an amount is text that is not a number, max_warranty_share is not a number from 0 to below 1, tolerance is not a number of zero or more, service_accounts is a string, or the service lines are in more than one currency while the frame has no amount_dkk.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import labour_absorption_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> jl = pd.DataFrame({"le_key": ["LE-A"] * 4, "period": ["2026-01"] * 4, "gl_key": ["GL-6100", "GL-7900", "GL-6610", "GL-7910"], "amount": [1000.0, -900.0, 100.0, -100.0]})
        >>> labour_absorption_check(jl, context=ctx)[["key", "rule", "detail"]].values.tolist()
        [['LE-A 2026-01', 'project_labour_not_absorbed', 'GL-6100 and GL-7900 net to 100.00, not zero']]
        >>> labour_absorption_check(jl.assign(amount=[1000.0, -1000.0, 100.0, -100.0]), context=ctx).empty
        True
    """
    _need(journal_line, ["le_key", "gl_key", "period", "amount"], "finance.journal_line")
    if not isinstance(max_warranty_share, (numbers.Real, Decimal, np.number)):
        raise FrameError(f"max_warranty_share must be a number from 0 to below 1, not {max_warranty_share!r}")
    if not 0 <= max_warranty_share < 1:
        raise FrameError("max_warranty_share must be from 0 to below 1")
    _tol_cents(tolerance)
    if isinstance(service_accounts, (str, bytes)):
        raise FrameError("service_accounts must be a tuple of accounts")
    if journal_line["le_key"].isna().any():
        raise FrameError("finance.journal_line has a row without an le_key")
    x = journal_line[journal_line["gl_key"].isin([project_labour, project_absorbed, service_absorbed, *service_accounts])]
    _numeric(x, ["amount", *(["amount_dkk"] if "amount_dkk" in x.columns else [])], "finance.journal_line")
    c = pd.DataFrame({"le_key": x["le_key"].to_numpy(), "period": x["period"].astype(str).to_numpy(), "gl": x["gl_key"].astype(str).to_numpy(), "c": _cents(x["amount"])})
    sv = x[x["gl_key"].isin([service_absorbed, *service_accounts])]
    if "amount_dkk" in x.columns:
        c["d"] = _cents(x["amount_dkk"])
    elif "currency" in sv.columns and sv["currency"].astype(str).nunique() > 1:
        raise FrameError("the service lines are in more than one currency: pass amount_dkk, the window sum would mix DKK and EUR")
    else:
        c["d"] = c["c"]
    rows = []
    p = c[c["gl"].isin([project_labour, project_absorbed])].groupby(["le_key", "period"])["c"].sum()
    for (le, per), v in cast(Any, p[p.abs() > _tol_cents(tolerance)]).items():
        rows.append(("finance.journal_line", f"{le} {per}", "project_labour_not_absorbed", f"{project_labour} and {project_absorbed} net to {v / 100:.2f}, not zero"))
    svc = int(c.loc[c["gl"].isin(service_accounts), "d"].sum())
    absorbed = -int(c.loc[c["gl"] == service_absorbed, "d"].sum())
    if svc > absorbed + _tol_cents(tolerance) or absorbed - svc > max_warranty_share * absorbed + _tol_cents(tolerance):
        rows.append(("finance.journal_line", "window", "service_labour_not_absorbed", f"service labour {svc / 100:.2f}, absorbed to service {absorbed / 100:.2f}: the rest {(absorbed - svc) / 100:.2f} is outside 0 to {max_warranty_share:.0%} of the absorbed amount"))
    return violations.frame(rows)


@staged(sources=("finance.cost_centre.cc_key", "finance.cost_centre.team_key", "hr.team.team_key", "hr.team.cost_centre_key"), oracle="py:repo_tests/test_oracle_payroll_release.py::test_oracle_cost_centre_team_map_baseline_against_pair_set_differences")
def cost_centre_team_map(cost_centre: pd.DataFrame, team: pd.DataFrame) -> pd.DataFrame:
    """Use this when you check that finance cost centres and hr teams point at each other.

    Rule: finance.cost_centre.team_key and hr.team.cost_centre_key are compared both ways. A cost centre without a team key (overhead) is not a violation.

    Args:
        cost_centre: Frame finance.cost_centre with cc_key and team_key, one row per cost centre.
        team: Frame hr.team with team_key and cost_centre_key, one row per team.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with table, key, rule and detail: cost_centre_without_team (a team key that hr does not have), team_without_cost_centre (an hr team whose cost centre finance does not have) and cost_centre_team_mismatch (the two views name different partners); empty when they agree.

    Raises:
        FrameError: a column is missing or a frame has more than one row for a key.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import cost_centre_team_map
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cost_centre = pd.DataFrame({"cc_key": ["CC-1", "CC-2"], "team_key": ["TEAM-1", "TEAM-9"]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-1", "TEAM-2"], "cost_centre_key": ["CC-1", "CC-3"]})
        >>> cost_centre_team_map(cost_centre, team, context=ctx)[["key", "rule"]].values.tolist()
        [['CC-2', 'cost_centre_without_team'], ['TEAM-2', 'team_without_cost_centre']]
    """
    _need(cost_centre, ["cc_key", "team_key"], "finance.cost_centre")
    _need(team, ["team_key", "cost_centre_key"], "hr.team")
    if cost_centre["cc_key"].duplicated().any() or team["team_key"].duplicated().any():
        raise FrameError("finance.cost_centre and hr.team need one row per key")
    rows = []
    t2c = team.set_index("team_key")["cost_centre_key"]
    cc_teams = cost_centre.dropna(subset=["team_key"]).set_index("cc_key")["team_key"]
    for cc, tk in cc_teams.items():
        if tk not in t2c.index:
            rows.append(("finance.cost_centre", cc, "cost_centre_without_team", f"team {tk} is not in hr.team"))
        elif t2c[tk] != cc:
            rows.append(("finance.cost_centre", cc, "cost_centre_team_mismatch", f"finance says team {tk}, hr says cost centre {t2c[tk]} for that team"))
    known = set(cost_centre["cc_key"])
    for tk, cc in t2c.items():
        if cc not in known:
            rows.append(("hr.team", tk, "team_without_cost_centre", f"cost centre {cc} is not in finance.cost_centre"))
        elif cc_teams.get(cc) != tk:
            rows.append(("hr.team", tk, "cost_centre_team_mismatch", f"hr says cost centre {cc}, finance says team {cc_teams.get(cc)} for that cost centre"))
    return violations.frame(rows)
