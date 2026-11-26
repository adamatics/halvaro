"""Payroll aggregate for halvaro-finance (plan 5.5 tie-out): pay per cost centre and month without employee keys. Pay is restricted: the role must read it, small groups are held back."""
from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import Context, FrameError, RestrictedColumnRefusal, fact, require_columns
from halvaro.core.registry import function

from .certs import _days
from .org import PolicyDefault

PAY = "base_salary"
PAY_ID = "hr.employment_term.base_salary"
_MIN = PolicyDefault("policy.pay_gap.minimum_cohort_size")
POOLED = "POOLED"      # cc_key of the row that adds up the cost centres under the minimum group size of one entity, currency and month
_SOURCES = (PAY_ID, "hr.employment_term.fte", "hr.employment_term.currency", "hr.employment_term.team_key", "hr.employment_term.grade_key", "hr.employment_term.valid_from",
            "hr.employment_term.valid_to", "hr.team.cost_centre_key", "hr.team.legal_entity_key", "hr.grade.band_min_dkk", "hr.grade.band_max_dkk", "hr.grade.band_min_eur", "hr.grade.band_max_eur")
_COLS = ["le_key", "cc_key", "period", "currency", "hr_gross_pay", "hr_headcount_month_end", "hr_fte", "band_minimum_total", "band_maximum_total", "n_people", "n_cost_centres", "cost_centres", "suppressed"]
_NUM = ["hr_gross_pay", "hr_headcount_month_end", "hr_fte", "band_minimum_total", "band_maximum_total"]


def _month_text(value: Any, name: str) -> pd.Period:
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-" or not (value[:4].isascii() and value[:4].isdigit() and value[5:].isascii() and value[5:].isdigit()) or not 1 <= int(value[5:]) <= 12:
        raise FrameError(f"{name} must be a period text like 2025-12, not {value!r}")
    return pd.Period(value, "M")


@function(sources=_SOURCES, restricted=(PAY_ID,), oracle="py:halvaro_gen/world/finance/registers.py::payroll_hr_reconciliation", facts=("policy.pay_gap.minimum_cohort_size",))
def payroll_aggregate(term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, first_month: str, last_month: str, *, minimum_group: int | PolicyDefault = _MIN,
                      on_small: str = "pool", context: Context) -> pd.DataFrame:
    """Use this when you need the gross pay of the employment terms per legal entity, cost centre, month and currency, without employee keys and without base salary, for the tie-out with finance.

    Rule: pay is restricted, so the context must be allowed to read hr.employment_term.base_salary. For each month from first_month to last_month, each term in force in the month (valid_from to valid_to inclusive; an empty valid_to is open) weighs days in force over days in the month; terms are grouped by the legal entity and cost centre of their team and by currency. A group with fewer than minimum_group distinct people is small: on_small 'pool' (default) adds the small cost centres of one entity, currency and month into one row with cc_key POOLED, which is itself suppressed when it still has fewer people; 'suppress' keeps each small group with null numbers; 'refuse' raises. Suppressed rows have null numbers. Without suppression the total over all rows equals the sum over the terms. Months without a term give no row. A grade band value that is null adds 0 to the band totals (the sum skips nulls), and a term with valid_to before valid_from is accepted but has weight 0, so it is left out of the month (no row of its own, not counted in n_people).

    Args:
        term: Employment terms (hr.employment_term) with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency (DKK or EUR) and base_salary; fte above zero, no nulls except valid_to.
        team: Teams (hr.team) with team_key, cost_centre_key and legal_entity_key, one row per team.
        grade: Grades (hr.grade) with gra_key, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per grade.
        first_month: The first month as text, YYYY-MM.
        last_month: The last month as text, YYYY-MM; not before first_month.
        minimum_group: The smallest number of people a group may show, a whole number of one or more (default the fact policy.pay_gap.minimum_cohort_size, status proposed; the status then goes into attrs["policy_status"]).
        on_small: What to do with a small group: 'pool', 'suppress' or 'refuse'.
        context: The caller (stage, role and whether restricted columns may be read); the role must be allowed to read pay.

    Returns:
        pandas.DataFrame with le_key, cc_key, period (YYYY-MM), currency, hr_gross_pay (base salary times fte times days in force over days in the month, the rule of finance.payroll_hr_reconciliation), hr_headcount_month_end (terms in force on the last day of the month), hr_fte (fte weighted by days), band_minimum_total and band_maximum_total (grade band times weighted fte, in the currency of the term), n_people (distinct people with a term in the month), n_cost_centres, cost_centres (the cost centre keys of the group, comma separated: one key, or the members of a POOLED row) and suppressed, sorted by le_key, cc_key, period and currency.

    Raises:
        RestrictedColumnRefusal: the context may not read base salary, or term has no base_salary column.
        FrameError: context is not a Context (None, text), fte or base_salary holds text, on_small or minimum_group is invalid, a month is not YYYY-MM or first_month is after last_month, a frame lacks a column, hr.team or hr.grade has a duplicate key, term has missing values, a currency other than DKK or EUR or an fte of zero or less, a term names a team or grade that is not in hr.team or hr.grade, a date is not a date, a policy default is not a whole number, or on_small is 'refuse' and a group is small.
        FactNotFound: the default minimum group is used and its fact is not in the snapshot.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.hr import payroll_aggregate
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "valid_from": ["2025-01-01", "2026-01-16"], "valid_to": [None, None], "team_key": ["TEAM-01"] * 2,
        ...                      "grade_key": ["GRA-01"] * 2, "fte": [1.0, 1.0], "currency": ["DKK"] * 2, "base_salary": [100.0, 100.0]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-01"], "cost_centre_key": ["CC-01"], "legal_entity_key": ["LE-01"]})
        >>> grade = pd.DataFrame({"gra_key": ["GRA-01"], "band_min_dkk": [50.0], "band_max_dkk": [150.0], "band_min_eur": [7.0], "band_max_eur": [20.0]})
        >>> reader = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> shown = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=2, context=reader)
        >>> shown[["cc_key", "period", "hr_headcount_month_end", "n_people", "suppressed"]].to_dict("records")
        [{'cc_key': 'CC-01', 'period': '2026-01', 'hr_headcount_month_end': 2.0, 'n_people': 2, 'suppressed': False}]
        >>> round(float(shown["hr_fte"].iloc[0]), 3)
        1.516
        >>> held = payroll_aggregate(term, team, grade, "2026-01", "2026-01", minimum_group=3, context=reader)
        >>> held[["cc_key", "n_people", "suppressed"]].to_dict("records"), bool(held["hr_fte"].isna().all())
        ([{'cc_key': 'POOLED', 'n_people': 2, 'suppressed': True}], True)
    
    """
    if not isinstance(context, Context):
        raise FrameError(f"halvaro.hr.payroll.payroll_aggregate needs context= a halvaro.core.Context (stage and role of the session), not {type(context).__name__}")
    require_columns(context, [PAY_ID])
    if PAY not in term.columns:
        raise RestrictedColumnRefusal(PAY_ID, context.role, context.stage)
    if on_small not in ("pool", "suppress", "refuse"):
        raise FrameError("on_small is 'pool', 'suppress' or 'refuse'")
    used: dict[str, Any] = {}
    mg = minimum_group
    if isinstance(minimum_group, PolicyDefault):
        f = fact(minimum_group.fact_id)
        if isinstance(f.value, bool) or not isinstance(f.value, (int, float)) or not float(f.value).is_integer():
            raise FrameError(f"{minimum_group.fact_id} must be a whole number of people, it is {f.value!r}")
        mg, used[minimum_group.fact_id] = int(f.value), f.status
    if isinstance(mg, bool) or not isinstance(mg, (int, np.integer)) or mg < 1:
        raise FrameError(f"minimum_group must be a whole number of people, one or more, not {minimum_group!r}")
    p0, p1 = _month_text(first_month, "first_month"), _month_text(last_month, "last_month")
    if p0 > p1:
        raise FrameError("first_month is after last_month")
    miss = [c for c in ("emp_key", "valid_from", "valid_to", "team_key", "grade_key", "fte", "currency", PAY) if c not in term.columns]
    if miss:
        raise FrameError(f"hr.employment_term frame lacks column(s) {', '.join(miss)}")
    for df, cols, what in ((team, ["team_key", "cost_centre_key", "legal_entity_key"], "hr.team"), (grade, ["gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"], "hr.grade")):
        m = [c for c in cols if c not in df.columns]
        if m:
            raise FrameError(f"{what} frame lacks column(s) {', '.join(m)}")
    if team["team_key"].duplicated().any() or grade["gra_key"].duplicated().any():
        raise FrameError("hr.team and hr.grade need one row per key")
    if term[["emp_key", "team_key", "grade_key", "fte", "currency", "valid_from"]].isna().any().any() or term[PAY].isna().any():
        raise FrameError("hr.employment_term has missing keys, fte, currency, valid_from or base salary")
    try:
        small_fte = (term["fte"] <= 0).any()
        _ = term[PAY] * 1.0
    except TypeError:
        raise FrameError("hr.employment_term fte and base_salary must be numbers, not text") from None
    if not term["currency"].isin(["DKK", "EUR"]).all() or small_fte:
        raise FrameError("hr.employment_term needs currency DKK or EUR and fte above zero")
    t = _days(term[["emp_key", "valid_from", "valid_to", "team_key", "grade_key", "fte", "currency", PAY]], ["valid_from", "valid_to"], "hr.employment_term")
    t = t.merge(team[["team_key", "cost_centre_key", "legal_entity_key"]], on="team_key", how="left", validate="many_to_one").merge(
        grade[["gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"]], left_on="grade_key", right_on="gra_key", how="left", validate="many_to_one")
    if t["cost_centre_key"].isna().any() or t["gra_key"].isna().any():
        raise FrameError("employment terms with a team or grade that is not in hr.team or hr.grade")
    eur = (t["currency"] == "EUR").to_numpy()
    t["lo"] = np.where(eur, t["band_min_eur"], t["band_min_dkk"]).astype(float)
    t["hi"] = np.where(eur, t["band_max_eur"], t["band_max_dkk"]).astype(float)
    t = t.drop(columns=["gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"])
    rows = []
    for per in pd.period_range(p0, p1, freq="M"):
        s0, end0 = per.start_time.normalize(), per.end_time.normalize()
        days = (end0 - s0).days + 1
        end = t["valid_to"].fillna(pd.Timestamp("2200-01-01"))
        ov = ((end.clip(upper=cast(Any, end0)) - t["valid_from"].clip(lower=cast(Any, s0))).dt.days + 1).clip(lower=0) / days
        x = t[ov > 0].assign(w=ov[ov > 0])
        if x.empty:
            continue
        x["pay"], x["fte_w"] = x[PAY] * x["fte"] * x["w"], x["fte"] * x["w"]
        x["lo_t"], x["hi_t"] = x["lo"] * x["fte_w"], x["hi"] * x["fte_w"]
        x["hc"] = ((x["valid_from"] <= end0) & (x["valid_to"].isna() | (x["valid_to"] >= end0))).astype(int)
        x["period"] = str(per)
        rows.append(x[["legal_entity_key", "cost_centre_key", "period", "currency", "emp_key", "pay", "fte_w", "lo_t", "hi_t", "hc"]])
    cols_in = ["legal_entity_key", "cost_centre_key", "period", "currency"]
    if not rows:
        out = pd.DataFrame(columns=_COLS)
        out.attrs["policy_status"] = used
        return out
    x = pd.concat(rows, ignore_index=True)
    agg = lambda d, keys: d.groupby(keys, as_index=False).agg(hr_gross_pay=("pay", "sum"), hr_headcount_month_end=("hc", "sum"), hr_fte=("fte_w", "sum"), band_minimum_total=("lo_t", "sum"),
                                                             band_maximum_total=("hi_t", "sum"), n_people=("emp_key", "nunique"), n_cost_centres=("cost_centre_key", "nunique"),
                                                             cost_centres=("cost_centre_key", lambda v: ",".join(sorted(set(v)))))
    g = agg(x, cols_in)
    small = g["n_people"] < mg
    if small.any() and on_small == "refuse":
        raise FrameError(f"{int(small.sum())} cost centre months have fewer than {mg} people; pay is not shown for such a group (on_small='pool' adds them up)")
    keep = g[~small]
    if on_small == "pool" and small.any():
        key = x.merge(g[small][cols_in], on=cols_in, how="inner")
        pooled = agg(key, ["legal_entity_key", "period", "currency"]).assign(cost_centre_key=POOLED)
        g = pd.concat([keep, pooled[g.columns]], ignore_index=True)
    out = g.rename(columns={"legal_entity_key": "le_key", "cost_centre_key": "cc_key"})
    out["suppressed"] = out["n_people"] < mg
    out.loc[out["suppressed"], _NUM] = np.nan
    out = out[_COLS].sort_values(["le_key", "cc_key", "period", "currency"]).reset_index(drop=True)
    if used:
        out.attrs["policy_status"] = used
    return cast(pd.DataFrame, out)
