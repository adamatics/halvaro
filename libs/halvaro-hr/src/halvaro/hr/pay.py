"""Pay differences between women and men. Pay is restricted: the person frame needs a role with access, results are aggregates, small cells are suppressed."""
from __future__ import annotations

import datetime as dt
import warnings
from typing import Any, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import Context, FrameError, RestrictedColumnRefusal, combine_status, fact, require_columns, rows_on
from halvaro.core.registry import function

from ._guard import stage_check
from .certs import _check_education

PAY = "base_salary"
PAY_ID = "hr.employment_term.base_salary"
_FX = "world.fx_eur_dkk_fixed"
_THRESHOLD = "legal.pay_transparency.joint_assessment_gap_threshold"
_SOURCES = (PAY_ID, "hr.employment_term.fte", "hr.employment_term.currency", "hr.employee.gender", "hr.employee.hire_date", "hr.employee.legal_entity_key",
            "hr.team.dep_key", "hr.grade.level")
_GENDERS = ("F", "M")        # the data has two values (plan 9); other values are left out of every gap
_MIN_DOF = 2                 # residual degrees of freedom the OLS needs beyond its columns


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}")


def _pay_input(frame: pd.DataFrame, columns: Sequence[str], context: Context | None) -> pd.DataFrame:
    """Guard of the aggregate functions: the role must read pay when a context is given, the pay columns must exist, only F and M rows count."""
    if context is not None:
        require_columns(context, [PAY_ID])
    missing = [c for c in columns if c not in frame.columns]
    if missing and any(c in ("rate_dkk", "compa") for c in missing):
        raise RestrictedColumnRefusal(PAY_ID, getattr(context, "role", "a role without access (the frame has no pay columns)"), getattr(context, "stage", "day1"))
    _need(frame, columns, "pay frame (from pay_frame)")
    return frame[frame["gender"].isin(_GENDERS)]


@function(sources=_SOURCES + ("hr.grade.band_min_dkk", "hr.grade.band_max_dkk", "hr.grade.band_min_eur", "hr.grade.band_max_eur"), restricted=(PAY_ID,), facts=(_FX,),
          oracle="py:halvaro_gen/truth/hr.py::pay_frame")
def pay_frame(employee: pd.DataFrame, term: pd.DataFrame, team: pd.DataFrame, grade: pd.DataFrame, as_of: dt.date, *, context: Context, bands_year: int = 2026) -> pd.DataFrame:
    """Use this when you need the person frame on a date with the monthly full-time rate, tenure and position in the pay band; it is the input of every pay difference function.

    Rule: the terms valid on the date, with rate_local = base_salary over fte; rate_dkk is rate_local for a DKK term and rate_local times the fixed EUR to DKK rate (a fact) for an EUR term. tenure_years is the days from hire_date to as_of over 365.25; compa is rate_local over the band midpoint in the currency of the term. base_salary itself is not returned. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning in attrs["warnings"] says that compa is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        employee: Employee frame with emp_key, gender, hire_date and legal_entity_key.
        term: Employment term frame with emp_key, valid_from, valid_to, team_key, grade_key, fte, currency and base_salary.
        team: Team frame with team_key and dep_key.
        grade: Grade frame with gra_key, level and the DKK and EUR band minimum and maximum.
        as_of: The date the frame describes.
        context: The caller; the role must be allowed to read pay (required keyword).
        bands_year: The year the grade bands are set at. Default 2026 (proposed).

    Returns:
        pandas.DataFrame: one row per valid term with the employee, team and grade columns, rate_local, rate_dkk, tenure_years and compa, and warnings in attrs.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the term frame has no base_salary.
        FrameError: a column is missing, a valid term has fte not above zero, a missing or infinite salary or a currency other than DKK and EUR, or a valid term has no employee, team or grade.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> import datetime as dt
        >>> from halvaro.hr import pay_frame
        >>> employee = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "hire_date": [dt.date(2020, 1, 1)], "legal_entity_key": ["LE-01"]})
        >>> term = pd.DataFrame({"emp_key": ["EMP-000001"], "valid_from": [dt.date(2020, 1, 1)], "valid_to": [None], "team_key": ["TEAM-1"], "grade_key": ["GRA-1"], "fte": [1.0],
        ...                       "currency": ["DKK"], "base_salary": [50000.0]})
        >>> team = pd.DataFrame({"team_key": ["TEAM-1"], "dep_key": ["DEP-01"]})
        >>> grade = pd.DataFrame({"gra_key": ["GRA-1"], "level": [3], "band_min_dkk": [40000.0], "band_max_dkk": [60000.0], "band_min_eur": [5000.0], "band_max_eur": [8000.0]})
        >>> frame = pay_frame(employee, term, team, grade, dt.date(2026, 6, 1), context=access)
        >>> frame[["rate_dkk", "compa"]].values.tolist()
        [[50000.0, 1.0]]
    """
    require_columns(context, [PAY_ID])
    if PAY not in term.columns:
        raise RestrictedColumnRefusal(PAY_ID, context.role, context.stage)
    _need(term, ["emp_key", "valid_from", "valid_to", "team_key", "grade_key", "fte", "currency"], "hr.employment_term")
    _need(employee, ["emp_key", "gender", "hire_date", "legal_entity_key"], "hr.employee")
    _need(grade, ["gra_key", "level", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"], "hr.grade")
    valid = rows_on(term, as_of, key="emp_key")
    if not (valid["fte"] > 0).all() or not np.isfinite(valid[PAY].astype(float)).all():
        raise FrameError("hr.employment_term has a non-positive fte or a missing or non-finite base_salary on this date; the rate cannot be computed")
    if not valid["currency"].isin(["DKK", "EUR"]).all():
        raise FrameError(f"currencies other than DKK and EUR in hr.employment_term: {sorted(set(valid['currency']) - {'DKK', 'EUR'})}")
    t = (valid.merge(employee[["emp_key", "gender", "hire_date", "legal_entity_key"]], on="emp_key", validate="one_to_one")
         .merge(team[["team_key", "dep_key"]], on="team_key", validate="many_to_one")
         .merge(grade[["gra_key", "level", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"]], left_on="grade_key", right_on="gra_key", validate="many_to_one"))
    if len(t) < len(valid):
        raise FrameError(f"{len(valid) - len(t)} valid terms have no employee, team or grade row; check the reference frames")
    fx = float(fact(_FX).value)
    eur = t["currency"] == "EUR"
    t["rate_local"] = t[PAY] / t["fte"]
    t["rate_dkk"] = np.where(eur, t["rate_local"] * fx, t["rate_local"])
    t["tenure_years"] = (pd.Timestamp(as_of) - pd.to_datetime(t["hire_date"])).dt.days / 365.25
    mid = np.where(eur, (t["band_min_eur"] + t["band_max_eur"]) / 2, (t["band_min_dkk"] + t["band_max_dkk"]) / 2)
    t["compa"] = t["rate_local"] / mid
    out = t.drop(columns=[PAY, "gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"]).reset_index(drop=True)
    msg = f"grade bands sit at the {bands_year} level: pay over band midpoint is understated before {bands_year}" if as_of.year < bands_year else None
    out.attrs["warnings"] = [msg] if msg else []
    if msg:
        warnings.warn(msg, UserWarning, stacklevel=2)
    return out


@function(sources=_SOURCES + ("hr.grade.band_min_dkk", "hr.grade.band_max_dkk", "hr.grade.band_min_eur", "hr.grade.band_max_eur"), restricted=(PAY_ID,), facts=(_FX,))
def band_position(frame: pd.DataFrame, grade: pd.DataFrame, *, context: Context, as_of: dt.date | None = None, bands_year: int = 2026) -> pd.DataFrame:
    """Use this when you want to see where each person's pay lies in the band of the grade, in the currency of the person's term.

    Rule: vs_midpoint is the rate over the band midpoint (the compa ratio); position_in_band is (rate less band minimum) over (maximum less minimum), so below 0 or above 1 is outside the band; in_band says whether it is inside. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning says that the position is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with emp_key, gender (only F and M rows count), grade_key, currency, rate_local and compa.
        grade: Grade frame (hr.grade) with gra_key and the band limits in DKK and EUR.
        context: The caller; the role must be allowed to read pay.
        as_of: The date the position is read at. Optional.
        bands_year: The year the bands are set at. Default 2026 (proposed).

    Returns:
        pandas.DataFrame with emp_key, grade_key, currency, rate_local, band_min, band_mid, band_max, vs_midpoint, position_in_band and in_band.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: a column is missing, a grade is held twice or not at all, a term is not in DKK or EUR, or a band maximum is not above its minimum.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import band_position
        >>> people = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "grade_key": ["GRA-4"], "currency": ["DKK"], "rate_local": [45000.0], "compa": [1.0]})
        >>> grade = pd.DataFrame({"gra_key": ["GRA-4"], "level": [4], "band_min_dkk": [40000.0], "band_max_dkk": [50000.0], "band_min_eur": [5000.0], "band_max_eur": [6700.0]})
        >>> band_position(people, grade, context=access)[["band_mid", "vs_midpoint", "position_in_band", "in_band"]].values.tolist()
        [[45000.0, 1.0, 0.5, True]]
    """
    require_columns(context, [PAY_ID])
    f = _pay_input(frame, ("emp_key", "grade_key", "currency", "rate_local", "compa"), context)
    _need(grade, ["gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"], "hr.grade")
    if grade["gra_key"].duplicated().any():
        raise FrameError("hr.grade has more than one row for a grade")
    if not f["currency"].isin(["DKK", "EUR"]).all():
        raise FrameError("band_position takes terms in DKK or EUR")
    t = f.merge(grade[["gra_key", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"]], left_on="grade_key", right_on="gra_key", how="left", validate="many_to_one")
    if t["gra_key"].isna().any():
        raise FrameError(f"{int(t['gra_key'].isna().sum())} people have a grade that hr.grade does not hold")
    eur = (t["currency"] == "EUR").to_numpy()
    lo, hi = np.where(eur, t["band_min_eur"], t["band_min_dkk"]).astype(float), np.where(eur, t["band_max_eur"], t["band_max_dkk"]).astype(float)
    if not (hi > lo).all():
        raise FrameError("a grade band has a maximum that is not above its minimum")
    mid = (lo + hi) / 2
    rate = t["rate_local"].astype(float).to_numpy()
    out = pd.DataFrame({"emp_key": t["emp_key"].to_numpy(), "grade_key": t["grade_key"].to_numpy(), "currency": t["currency"].to_numpy(), "rate_local": rate, "band_min": lo, "band_mid": mid, "band_max": hi,
                        "vs_midpoint": rate / mid, "position_in_band": (rate - lo) / (hi - lo)})
    out["in_band"] = (rate >= lo) & (rate <= hi)
    msg = f"grade bands sit at the {bands_year} level: the band position is understated before {bands_year}" if (as_of is not None and as_of.year < bands_year) else None
    out.attrs["warnings"] = [msg] if msg else []
    if msg:
        warnings.warn(msg, UserWarning, stacklevel=2)
    return out.sort_values("emp_key").reset_index(drop=True)


@function(sources=_SOURCES, restricted=(PAY_ID,), oracle="py:halvaro_gen/truth/hr.py::gap_stats")
def raw_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> float:
    """Use this when you need the raw pay difference between women and men: how much less the women are paid on average, before any adjustment.

    Rule: one minus the mean rate of women over the mean rate of men, in percent; positive means women are paid less. The result is NaN when either gender has fewer than minimum_group people (proposed 8). The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with gender and rate_dkk; only F and M rows count.
        minimum_group: The smallest number of people per gender. Default 8 (proposed).
        context: The caller; with it the role must be allowed to read pay. Optional keyword.

    Returns:
        float: the gap in percent, or NaN below the minimum group size.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: the frame lacks the column gender.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import raw_gap
        >>> people = pd.DataFrame({"gender": ["F", "F", "M", "M"], "rate_dkk": [90.0, 110.0, 190.0, 210.0]})
        >>> raw_gap(people, minimum_group=2, context=access)
        50.0
    """
    f = _pay_input(frame, ("gender", "rate_dkk"), context)
    w, m = f[f["gender"] == "F"], f[f["gender"] == "M"]
    if min(len(w), len(m)) < minimum_group:
        return float("nan")
    return float((1 - w["rate_dkk"].mean() / m["rate_dkk"].mean()) * 100)


def _ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    s2 = float(res @ res) / max(1, len(y) - X.shape[1])
    return b, np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))


@function(sources=_SOURCES, restricted=(PAY_ID,), oracle="py:halvaro_gen/truth/hr.py::gap_stats")
def adjusted_gap(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None, extra_controls: str | Sequence[str] = ()) -> dict[str, Any]:
    """Use this when you need the pay difference between women and men after taking tenure, legal entity and grade into account, with its standard error.

    Rule: an OLS of ln(rate_dkk) on a dummy for women, tenure, one indicator per legal entity and one per grade; the gap is (1 minus exp(b)) times 100 in percent, positive when women are paid less. The result is suppressed (NaN, suppressed True) below minimum_group people per gender (proposed 8), when the sample is too small for the model, and for nothing else. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key and level.
        minimum_group: The smallest number of people per gender. Default 8 (proposed).
        context: The caller; with it the role must be allowed to read pay. Optional keyword.
        extra_controls: Names of numeric columns added to the model, for instance education_rank from with_education. Default none.

    Returns:
        dict: n_women, n_men, adjusted_gap_pct and adjusted_gap_se_pct (percent, NaN when suppressed), suppressed (bool) and legal_status.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: a column is missing, an extra control is not numeric, infinite, missing, repeated or already in the model, or the rate, entity, grade or tenure values are missing or not valid.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import adjusted_gap
        >>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6})
        >>> result = adjusted_gap(people, minimum_group=3, context=access)
        >>> result["n_women"], result["n_men"], result["suppressed"], round(result["adjusted_gap_pct"], 1)
        (3, 3, False, 9.1)
        >>> adjusted_gap(people, context=access)["suppressed"]
        True
    """
    extra = [extra_controls] if isinstance(extra_controls, str) else list(extra_controls)
    own = {"gender", "rate_dkk", "tenure_years", "legal_entity_key", "level", "rate_local"}
    bad = [c for c in extra if c in own or extra.count(c) > 1]
    if bad:
        raise FrameError(f"extra_controls {sorted(set(bad))} is already a column of the model or the pay or is given twice")
    for c in extra:
        if c in frame.columns and not pd.api.types.is_numeric_dtype(frame[c]):
            raise FrameError(f"extra control {c} must be numeric")
        if c in frame.columns and not np.isfinite(frame[c].astype(float).fillna(0)).all():
            raise FrameError(f"extra control {c} has infinite values")
    f = _pay_input(frame, ("gender", "rate_dkk", "tenure_years", "legal_entity_key", "level", *extra), context)
    w, m = int((f["gender"] == "F").sum()), int((f["gender"] == "M").sum())
    nan = float("nan")
    out = {"n_women": w, "n_men": m, "adjusted_gap_pct": nan, "adjusted_gap_se_pct": nan, "suppressed": True, "legal_status": combine_status([])}
    if min(w, m) < minimum_group:
        return out
    if extra and f[extra].isna().any().any():
        raise FrameError(f"extra control(s) {', '.join(c for c in extra if f[c].isna().any())} have missing values")
    if f[["legal_entity_key", "level", "tenure_years"]].isna().any().any() or not np.isfinite(f["rate_dkk"].astype(float)).all() or (f["rate_dkk"] <= 0).any():
        raise FrameError("the pay frame has missing entity, grade or tenure values or a non-positive or non-finite rate")
    ents = sorted(f["legal_entity_key"].unique())[1:]
    X = np.column_stack([np.ones(len(f)), (f["gender"] == "F").astype(float), f["tenure_years"]]
                        + [(f["legal_entity_key"] == e).astype(float) for e in ents] + [(f["level"] == g).astype(float) for g in sorted(f["level"].unique())[1:]]
                        + [f[c].astype(float) for c in extra])
    if len(f) <= X.shape[1] + _MIN_DOF:
        return out
    b, se = _ols(np.log(f["rate_dkk"].to_numpy(dtype=float)), X)
    out.update(adjusted_gap_pct=float((1 - np.exp(b[1])) * 100), adjusted_gap_se_pct=float(se[1] * 100), suppressed=False)
    return out


@function(sources=_SOURCES, restricted=(PAY_ID,), facts=(_THRESHOLD,))
def gap_table(frame: pd.DataFrame, by: str = "department", *, minimum_group: int = 8, watch: float = 0.03, context: Context | None = None) -> pd.DataFrame:
    """Use this when you want the pay difference between women and men per department or per grade in one table, with a flag for each group and a ranking.

    Rule: for each group the counts, the raw gap (raw_gap) and the adjusted gap (adjusted_gap) in percent. The flag is above_threshold at or above the legal joint assessment threshold (a fact), watch at or above watch times 100 percent (proposed 0.03), otherwise ok. A group under minimum_group people per gender (proposed 8) keeps its counts, loses the gaps, is flagged suppressed and has no rank. The rank is by adjusted gap, highest first. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with gender, rate_dkk, tenure_years, legal_entity_key, level and the grouping column (dep_key or level).
        by: Either department (groups by dep_key) or grade (groups by level). Default department.
        minimum_group: The smallest number of people per gender. Default 8 (proposed).
        watch: The share at or above which a group is flagged watch. Default 0.03 (proposed).
        context: The caller; with it the role must be allowed to read pay. Optional keyword.

    Returns:
        pandas.DataFrame: one row per group with the key column, n_women, n_men, raw_gap_pct, adjusted_gap_pct, adjusted_gap_se_pct, flag, suppressed, rank and legal_status.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: by is not department or grade, or a column is missing.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import gap_table
        >>> people = pd.DataFrame({"gender": ["F"] * 3 + ["M"] * 3, "rate_dkk": [180.0, 200.0, 220.0, 200.0, 220.0, 240.0], "tenure_years": [1.0, 2.0, 3.0] * 2, "legal_entity_key": ["LE-01"] * 6, "level": [3] * 6, "dep_key": ["DEP-01"] * 6})
        >>> table = gap_table(people, minimum_group=3, context=access)
        >>> table[["dep_key", "n_women", "n_men", "suppressed"]].values.tolist(), round(float(table["raw_gap_pct"].iloc[0]), 1)
        ([['DEP-01', 3, 3, False]], 9.1)
        >>> gap_table(people, context=access)["flag"].tolist()
        ['suppressed']
    """
    key = {"department": "dep_key", "grade": "level"}.get(by)
    if key is None:
        raise FrameError(f"by {by!r} is not department or grade")
    f = _pay_input(frame, ("gender", "rate_dkk", "tenure_years", "legal_entity_key", "level", key), context)
    limit = float(fact(_THRESHOLD).value) * 100
    rows = []
    for k, g in f.groupby(key):
        a = adjusted_gap(g, minimum_group)
        sup, adj = a["suppressed"], a["adjusted_gap_pct"]
        raw = float("nan") if sup else raw_gap(g, minimum_group)
        flag = "suppressed" if sup else ("above_threshold" if adj >= limit else "watch" if adj >= watch * 100 else "ok")
        rows.append({key: k, "n_women": a["n_women"], "n_men": a["n_men"], "raw_gap_pct": raw, "adjusted_gap_pct": adj, "adjusted_gap_se_pct": a["adjusted_gap_se_pct"], "flag": flag,
                     "suppressed": sup})
    cols = [key, "n_women", "n_men", "raw_gap_pct", "adjusted_gap_pct", "adjusted_gap_se_pct", "flag", "suppressed"]
    out = pd.DataFrame(rows, columns=cols)
    out["_k"] = out["adjusted_gap_pct"].fillna(-np.inf)
    out = out.sort_values(["suppressed", "_k", key], ascending=[True, False, True]).drop(columns="_k").reset_index(drop=True)
    out["rank"] = pd.array([pd.NA if s else i + 1 for i, s in enumerate(out["suppressed"])], dtype="Int64")
    out["legal_status"] = combine_status([fact(_THRESHOLD).status])
    return out


@function(oracle="py:halvaro_gen/truth/hr.py::gap_stats")
def suppress_small_cells(table: pd.DataFrame, value_columns: str | Sequence[str], *, count_columns: Sequence[str] = ("n_women", "n_men"), minimum_group: int = 8) -> pd.DataFrame:
    """Use this when you publish a gap table and must hide the values of groups that are too small.

    Rule: in a row where any count is under minimum_group (proposed 8) or missing, the value columns are set to null; the flag becomes suppressed, the rank empty and the standard error null where those columns exist. The column suppressed only turns on, so suppressing twice gives the same table.

    Args:
        table: The gap table with the value columns and the count columns.
        value_columns: One column name or a list of names whose values are hidden for a small group.
        count_columns: The columns with the group sizes. Default n_women and n_men.
        minimum_group: The smallest group size that may be shown. Default 8 (proposed).

    Returns:
        pandas.DataFrame: a copy of the table with the small groups hidden and a boolean column suppressed.

    Raises:
        FrameError: the table lacks a value column or a count column.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import suppress_small_cells
        >>> table = pd.DataFrame({"group": ["a", "b"], "n_women": [10, 3], "n_men": [12, 9], "gap_pct": [1.5, 2.5]})
        >>> suppress_small_cells(table, ["gap_pct"])[["group", "gap_pct", "suppressed"]].astype(str).values.tolist()
        [['a', '1.5', 'False'], ['b', 'nan', 'True']]
    """
    cols = [value_columns] if isinstance(value_columns, str) else list(value_columns)
    _need(table, [*cols, *count_columns], "gap table")
    out = table.copy()
    small = ~(out[list(count_columns)] >= minimum_group).all(axis=1)
    out[cols] = out[cols].astype(float)
    out.loc[small, cols] = np.nan
    if "adjusted_gap_se_pct" in out:
        out.loc[small, "adjusted_gap_se_pct"] = np.nan
    if "flag" in out:
        out.loc[small, "flag"] = "suppressed"
    if "rank" in out:
        out["rank"] = out["rank"].astype("Int64")
        out.loc[small, "rank"] = pd.NA
    out["suppressed"] = (out["suppressed"].astype(bool) if "suppressed" in out else False) | cast(Any, small.values)
    return out


@function(sources=_SOURCES + ("hr.department.dep_code",), restricted=(PAY_ID,))
def intake_compa_by_grade(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8,
              context: Context | None = None) -> pd.DataFrame:
    """Use this when you want to compare women and men hired from a given date in one department, grade by grade, on their position in the pay band.

    Rule: among people in the department, hired on or after the date and in the given grades, the gap is (mean compa of women over mean compa of men minus 1) times 100; negative means women are below men. One row per grade and one row all for the pool. A row with fewer than minimum_group people (proposed 8) of one gender has NaN and suppressed True. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level and compa.
        dep: The department key (required).
        hired_from: The first hire date that counts (required: the caller decides which intake it asks about).
        grades: The grade levels that count (required).
        minimum_group: The smallest number of people per gender. Default 8 (proposed).
        context: The caller; with it the role must be allowed to read pay. Optional keyword.

    Returns:
        pandas.DataFrame: one row per grade plus all, with grade_level, n_women, n_men, women_vs_men_compa_pct (percent, NaN when suppressed), suppressed and legal_status.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: a column is missing.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> import datetime as dt
        >>> from halvaro.hr import intake_compa_by_grade
        >>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0]})
        >>> by_grade = intake_compa_by_grade(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), minimum_group=1, context=access)
        >>> by_grade[["grade_level", "n_women", "n_men"]].values.tolist()
        [[2, 1, 1], ['all', 1, 1]]
        >>> round(float(by_grade["women_vs_men_compa_pct"].iloc[0]), 6)
        -10.0
    """
    f = _pay_input(frame, ("gender", "dep_key", "hire_date", "level", "compa"), context)
    start = pd.Timestamp(hired_from)
    c = f[(f["dep_key"] == dep) & (pd.to_datetime(f["hire_date"]) >= start) & f["level"].isin(list(grades))]
    rows = []
    for label, g in [(int(cast(Any, lv)), grp) for lv, grp in c.groupby("level")] + [("all", c)]:
        w, m = g[g["gender"] == "F"], g[g["gender"] == "M"]
        sup = min(len(w), len(m)) < minimum_group
        pct = float("nan") if sup else float((w["compa"].mean() / m["compa"].mean() - 1) * 100)
        rows.append({"grade_level": label, "n_women": len(w), "n_men": len(m), "women_vs_men_compa_pct": pct, "suppressed": sup})
    out = pd.DataFrame(rows, columns=["grade_level", "n_women", "n_men", "women_vs_men_compa_pct", "suppressed"])
    out["legal_status"] = combine_status([])
    return out


@function(sources=_SOURCES + ("hr.department.dep_code",), restricted=(PAY_ID,))
def intake_pay_difference(frame: pd.DataFrame, *, hired_from: dt.date, dep: str, grades: tuple[int, ...], minimum_group: int = 8,
                    context: Context | None = None) -> dict[str, Any]:
    """Use this when you want to know whether the women hired from an intake date are paid differently from the men and from the other women of the same department.

    Rule: the by-grade frame of intake_compa_by_grade, and an OLS of ln(rate_dkk) on a dummy for women hired from the intake date, a dummy for the other women, tenure, entity and grade, over the whole department. The estimates are 100 times (exp(b) minus 1): negative when the women earn less (the sign of a pay level, not of adjusted_gap). The intake estimate is NaN with suppressed True when fewer than minimum_group women (proposed 8) were hired from the intake date or fewer men are in the department; the estimate of the other women is NaN when they number fewer than minimum_group. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame (the output of pay_frame) with gender, dep_key, hire_date, level, compa, rate_dkk, tenure_years and legal_entity_key.
        dep: The department key (required).
        hired_from: The first hire date of the intake (required: the caller decides which intake it asks about).
        grades: The grade levels of the by-grade frame (required).
        minimum_group: The smallest number of people per group. Default 8 (proposed).
        context: The caller; with it the role must be allowed to read pay. Optional keyword.

    Returns:
        dict: by_grade (the intake_compa_by_grade frame), n_intake_women, n_other_women, n_men, intake_women_pct and its se, other_women_pct and its se (percent), suppressed (bool) and legal_status.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        FrameError: a column is missing, or the rate, entity, grade or tenure values are missing or not valid.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> import datetime as dt
        >>> from halvaro.hr import intake_pay_difference
        >>> people = pd.DataFrame({"gender": ["F", "M"], "dep_key": ["DEP-07", "DEP-07"], "hire_date": [dt.date(2021, 6, 1)] * 2, "level": [2, 2], "compa": [0.9, 1.0],
        ...                         "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"]})
        >>> result = intake_pay_difference(people, hired_from=dt.date(2021, 4, 1), dep="DEP-07", grades=(2, 3), context=access)
        >>> result["suppressed"], result["n_intake_women"], result["n_men"]
        (True, 1, 1)
    """
    f = _pay_input(frame, ("gender", "dep_key", "hire_date", "level", "compa", "rate_dkk", "tenure_years", "legal_entity_key"), context)
    start = pd.Timestamp(hired_from)
    by_grade = intake_compa_by_grade(frame, dep=dep, hired_from=hired_from, grades=grades, minimum_group=minimum_group, context=context)
    d = f[f["dep_key"] == dep]
    intake = ((d["gender"] == "F") & (pd.to_datetime(d["hire_date"]) >= start)).to_numpy()
    other = ((d["gender"] == "F") & (pd.to_datetime(d["hire_date"]) < start)).to_numpy()
    nw, no, nm = int(intake.sum()), int(other.sum()), int((d["gender"] == "M").sum())
    nan = float("nan")
    out = {"by_grade": by_grade, "n_intake_women": nw, "n_other_women": no, "n_men": nm, "intake_women_pct": nan, "intake_women_se_pct": nan, "other_women_pct": nan,
           "other_women_se_pct": nan, "suppressed": True, "legal_status": combine_status([])}
    if nw < minimum_group or nm < minimum_group:
        return out
    if d[["legal_entity_key", "level", "tenure_years"]].isna().any().any() or not np.isfinite(d["rate_dkk"].astype(float)).all() or (d["rate_dkk"] <= 0).any():
        raise FrameError("the pay frame has missing entity, grade or tenure values or a non-positive or non-finite rate")
    ents = sorted(d["legal_entity_key"].unique())[1:]
    X = np.column_stack([np.ones(len(d)), intake.astype(float), other.astype(float), d["tenure_years"].astype(float)]
                        + [(d["legal_entity_key"] == e).astype(float) for e in ents] + [(d["level"] == g).astype(float) for g in sorted(d["level"].unique())[1:]])
    if len(d) <= X.shape[1] + _MIN_DOF:
        return out
    b, se = _ols(np.log(d["rate_dkk"].to_numpy(dtype=float)), X)
    out.update(intake_women_pct=float((np.exp(b[1]) - 1) * 100), intake_women_se_pct=float(se[1] * 100), suppressed=False)
    if no >= minimum_group:
        out.update(other_women_pct=float((np.exp(b[2]) - 1) * 100), other_women_se_pct=float(se[2] * 100))
    return out


@function(sources=_SOURCES + ("competence.education_record.emp_key", "competence.education_record.level_rank"), restricted=(PAY_ID,))
def with_education(frame: pd.DataFrame, education: pd.DataFrame, *, context: Context | None = None) -> pd.DataFrame:
    """Use this when you want the education level of each person next to the pay frame, so that it can be used as a control in the adjusted gap.

    Rule: education_rank is the highest level_rank of the person's education records and 0 without a record; has_education_record says which. People without a record are kept, so the control treats no record as rank 0. The input is not changed.

    Args:
        frame: A pay frame (the output of pay_frame) with emp_key.
        education: Education record frame (competence.education_record) with emp_key and level_rank.
        context: The caller. Optional keyword.

    Returns:
        pandas.DataFrame: the frame plus education_rank and has_education_record.

    Raises:
        RestrictedColumnRefusal: a context is given and its role may not read pay.
        StageRefusal: a context is given and its stage does not hold the pay and education sources.
        FrameError: a column is missing, the pay frame already has one of the new columns, or level_rank is not valid.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import with_education
        >>> people = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"]})
        >>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "level_rank": [2, 3]})
        >>> with_education(people, education, context=access)[["emp_key", "education_rank", "has_education_record"]].values.tolist()
        [['EMP-000001', 3, True], ['EMP-000002', 0, False]]
    """
    stage_check(context, ("hr.employment_term.base_salary", "competence.education_record.level_rank"), "halvaro.hr.pay.with_education")
    if context is not None:
        require_columns(context, [PAY_ID])
    _need(frame, ("emp_key",), "pay frame (from pay_frame)")
    _need(education, ("emp_key", "level_rank"), "competence.education_record")
    clash = [c for c in ("education_rank", "has_education_record") if c in frame.columns]
    if clash:
        raise FrameError(f"the pay frame already has column(s) {', '.join(clash)}")
    _check_education(education)
    top = education.groupby("emp_key")["level_rank"].max()
    out = frame.copy()
    out["has_education_record"] = out["emp_key"].isin(top.index)
    out["education_rank"] = out["emp_key"].map(top).fillna(0).astype(int)
    return out


@function(sources=_SOURCES + ("competence.education_record.level_rank",), restricted=(PAY_ID,))
def education_explained_share(frame: pd.DataFrame, minimum_group: int = 8, *, context: Context | None = None) -> dict[str, Any]:
    """Use this when you want to know how much of the adjusted pay difference goes away once education is taken into account.

    Rule: adjusted_gap without and with education_rank as a further control; explained_pp is gap without minus gap with, in percentage points. Everything is NaN with suppressed True below minimum_group people per gender (proposed 8). n_without_record counts people of the two genders with no education record. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

    Args:
        frame: A pay frame with education (the output of with_education).
        minimum_group: The smallest number of people per gender. Default 8 (proposed).
        context: The caller; with it the role must be allowed to read pay and education. Optional keyword.

    Returns:
        dict: n_women, n_men, gap_without_education_pct, gap_with_education_pct, explained_pp (percent and percentage points), n_without_record and suppressed.

    Raises:
        RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
        StageRefusal: the stage does not yet allow the pay and education sources.
        FrameError: education_rank or has_education_record is missing, or the frame fails adjusted_gap.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> access = Context(stage="month12", role="analyst", restricted_ok=True)
        >>> from halvaro.hr import education_explained_share
        >>> people = pd.DataFrame({"gender": ["F", "M"], "rate_dkk": [90.0, 100.0], "tenure_years": [1.0, 2.0], "legal_entity_key": ["LE-01", "LE-01"], "level": [3, 3],
        ...                         "education_rank": [2, 3], "has_education_record": [True, False]})
        >>> result = education_explained_share(people, context=access)
        >>> result["suppressed"], result["n_without_record"]
        (True, 1)
    """
    stage_check(context, ("hr.employment_term.base_salary", "competence.education_record.level_rank"), "halvaro.hr.pay.education_explained_share")
    _need(frame, ("education_rank", "has_education_record"), "pay frame with education (from with_education)")
    base = adjusted_gap(frame, minimum_group, context=context)
    out = {"n_women": base["n_women"], "n_men": base["n_men"], "gap_without_education_pct": base["adjusted_gap_pct"], "gap_with_education_pct": float("nan"),
           "explained_pp": float("nan"), "n_without_record": int((~frame.loc[frame["gender"].isin(_GENDERS), "has_education_record"].astype(bool)).sum()), "suppressed": base["suppressed"]}
    if base["suppressed"]:
        return out
    full = adjusted_gap(frame, minimum_group, context=context, extra_controls=("education_rank",))
    out["suppressed"] = bool(full["suppressed"])
    out["gap_with_education_pct"] = full["adjusted_gap_pct"]
    out["explained_pp"] = float("nan") if full["suppressed"] else base["adjusted_gap_pct"] - full["adjusted_gap_pct"]
    return out
