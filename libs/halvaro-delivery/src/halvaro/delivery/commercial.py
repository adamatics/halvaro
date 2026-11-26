"""Commercial view of the sales pipeline (plan 5.8): open tenders, the profile of a tender as the input of the comparable set, the customer carbon limit, win rate and the projects per customer.

Everything is read from crm.opportunity, crm.customer, the project frame and contracts.contract. A tender is open while its stage is in the open tender stages (PROPOSED: tender); the bid deadline is shown
with the days to it and a flag when it has passed, never used to hide a tender. Money is never converted here: values are the DKK column the crm table carries.
"""
from __future__ import annotations

from typing import Any, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._types import DateLike
from .projects import _day, _days

_OPP = ("crm.opportunity.opp_key", "crm.opportunity.cus_key", "crm.opportunity.stage", "crm.opportunity.is_open", "crm.opportunity.project_type", "crm.opportunity.country", "crm.opportunity.soil_class",
        "crm.opportunity.route_length_m", "crm.opportunity.bid_deadline")
_TIER_ORDER = ("anchor", "key", "standard", "occasional")
_DECIDED = ("won", "lost")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys and frame.duplicated(list(keys)).any():
        raise FrameError(f"{what} has more than one row for a {' and '.join(keys)}; one row per key is required")


def _strs(value: Any, name: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise FrameError(f"{name} must be a tuple or list of values, not {value!r}")
    return list(value)


@staged(sources=_OPP + ("crm.opportunity.requirements", "crm.opportunity.carbon_limit_kgco2e_per_m", "crm.opportunity.created_date", "crm.opportunity.name", "crm.opportunity.zone_key"),
        oracle="py:tests/test_crm.py::test_story_tenders")
def open_tenders(opportunity: pd.DataFrame, as_of: DateLike, stage_history: pd.DataFrame | None = None, *, stages: Sequence[str] = ("tender",)) -> pd.DataFrame:
    """Use this when you need the open opportunities in a tender stage on a day, with their profile, bid deadline and days to the deadline.

    Each row carries the profile fields, the bid deadline, the days to it (negative when it has passed) and `deadline_passed`, the requirements and the carbon limit. `stages` (tender, PROPOSED) names the stages that count as a tender; an opportunity created after the day is not listed. `asof_exact` is false when the stage is the one stored in the release (the day is only used for the created date and the deadline); with `stage_history` (crm.opportunity_stage_history) the stage on the day is the last stage entered on or before it, an opportunity counts as open when that stage is in `stages` or any other open stage is not needed, and `asof_exact` is true. A passed deadline is flagged, never used to hide a tender.

    Args:
        opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, name, cus_key, stage, is_open, project_type, country, soil_class, route_length_m, zone_key, bid_deadline, requirements, carbon_limit_kgco2e_per_m and created_date.
        as_of: The day to list the tenders for (a date, a Timestamp or an ISO text); a time of day is dropped.
        stage_history: Optional crm.opportunity_stage_history frame (opp_key, stage, entered_date, and seq when present); it gives the stage on the day.
        stages: The stage names that count as a tender, a tuple or list, not a text (default tender, PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns opp_key, name, cus_key, stage, asof_exact, project_type, country, soil_class, route_length_m, zone_key, bid_deadline, days_to_deadline, deadline_passed, requirements, carbon_limit_kgco2e_per_m, sorted by bid deadline (nulls last), then opp_key.

    Raises:
        PeriodError: as_of is a number, has a time zone or is not a date.
        FrameError: opportunity or stage_history is not a DataFrame, lacks a needed column or (opportunity) repeats an opp_key; stages is a text instead of a list; is_open has nulls; bid_deadline or entered_date is not a date or has a time zone; the stage history names an opportunity that crm.opportunity does not hold.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import open_tenders
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002"], "name": ["Tender A", "Tender B"], "cus_key": ["CUS-900001", "CUS-900001"],
        ...                     "stage": ["tender", "won"], "is_open": [True, False], "project_type": ["district_heating", "district_heating"],
        ...                     "country": ["DK", "DK"], "soil_class": ["clay", "clay"], "route_length_m": [1200.0, 800.0], "zone_key": ["ZONE-0001", "ZONE-0001"],
        ...                     "bid_deadline": ["2025-06-30", "2025-03-01"], "requirements": [None, None], "carbon_limit_kgco2e_per_m": [None, None],
        ...                     "created_date": ["2025-01-15", "2025-01-10"]})
        >>> r = open_tenders(opp, "2025-06-01", context=ctx)
        >>> r["opp_key"].tolist()
        ['OPP-900001']
        >>> r["days_to_deadline"].tolist()
        [29]"""
    _need(opportunity, ["opp_key", "name", "cus_key", "stage", "is_open", "project_type", "country", "soil_class", "route_length_m", "zone_key", "bid_deadline", "requirements",
                        "carbon_limit_kgco2e_per_m", "created_date"], "crm.opportunity", keys=("opp_key",))
    d = _day(as_of)
    st = _strs(stages, "stages")
    opportunity = opportunity.reset_index(drop=True)
    if opportunity["is_open"].isna().any():
        raise FrameError("crm.opportunity.is_open has nulls")
    created = pd.to_datetime(opportunity["created_date"]).dt.normalize()
    bd = _days(opportunity["bid_deadline"], "bid_deadline")
    if stage_history is not None:
        _need(stage_history, ["opp_key", "stage", "entered_date"], "crm.opportunity_stage_history")
        h = stage_history.assign(_e=_days(stage_history["entered_date"], "entered_date"))
        stray = sorted(set(stage_history["opp_key"]) - set(opportunity["opp_key"]))
        if stray:
            raise FrameError(f"crm.opportunity_stage_history names opportunities that crm.opportunity does not hold, for example {stray[0]}")
        h_stage = h[h["_e"] <= d].sort_values(["opp_key", "_e"] + (["seq"] if "seq" in h.columns else []), kind="stable").groupby("opp_key").tail(1).set_index("opp_key")["stage"]
        stage_asof = opportunity["opp_key"].map(h_stage)
        keep = stage_asof.isin(st) & (created <= d)
        x = opportunity[keep.to_numpy()].assign(stage=stage_asof[keep].to_numpy())
        exact = True
    else:
        keep = opportunity["is_open"].astype(bool) & opportunity["stage"].isin(st) & (created <= d)
        x = opportunity[keep.to_numpy()]
        exact = False
    bd = bd.loc[x.index]
    out = x[["opp_key", "name", "cus_key", "stage", "project_type", "country", "soil_class", "route_length_m", "zone_key"]].assign(
        asof_exact=exact, bid_deadline=bd, days_to_deadline=(bd - d).dt.days, deadline_passed=(bd < d).where(bd.notna(), cast(Any, None)), requirements=x["requirements"], carbon_limit_kgco2e_per_m=x["carbon_limit_kgco2e_per_m"])
    out = out[["opp_key", "name", "cus_key", "stage", "asof_exact", "project_type", "country", "soil_class", "route_length_m", "zone_key", "bid_deadline", "days_to_deadline", "deadline_passed", "requirements",
               "carbon_limit_kgco2e_per_m"]]
    return out.sort_values(["bid_deadline", "opp_key"], na_position="last").reset_index(drop=True)


@staged(sources=_OPP, oracle="py:tests/test_crm.py::test_story_tenders")
def tender_profile(opportunity: pd.DataFrame, opp_key: str) -> pd.Series:
    """Use this when you need one opportunity as the profile that is the input of comparable_set.

    Fields: opp_key, cus_key, type (the project type), country, soil_class, route_length_m, bid_deadline. The row is a Series, nothing is searched here. For the comparable set pass `{'country': row.country, 'type': row.type, 'soil_class': row.soil_class, ...}` as a profile mapping (a route window around the length is a caller's choice). A null length stays null.

    Args:
        opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, project_type, country, soil_class, route_length_m and bid_deadline.
        opp_key: The key of the opportunity as one text, for example OPP-900001.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series with the index opp_key, cus_key, type, country, soil_class, route_length_m and bid_deadline (a Timestamp, or NaT when there is none).

    Raises:
        FrameError: opportunity is not a DataFrame, lacks a needed column or repeats an opp_key; opp_key is not a single text; the opportunity is not in crm.opportunity.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import tender_profile
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opp = pd.DataFrame({"opp_key": ["OPP-900001"], "cus_key": ["CUS-900001"], "project_type": ["district_heating"], "country": ["DK"],
        ...                     "soil_class": ["clay"], "route_length_m": [1200.0], "bid_deadline": ["2025-06-30"]})
        >>> row = tender_profile(opp, "OPP-900001", context=ctx)
        >>> row["type"], row["country"], float(row["route_length_m"])
        ('district_heating', 'DK', 1200.0)"""
    _need(opportunity, ["opp_key", "cus_key", "project_type", "country", "soil_class", "route_length_m", "bid_deadline"], "crm.opportunity", keys=("opp_key",))
    if not isinstance(opp_key, str):
        raise FrameError("opp_key must be one text key")
    r = opportunity[opportunity["opp_key"] == opp_key]
    if r.empty:
        raise FrameError(f"opportunity {opp_key} is not in crm.opportunity")
    r = cast(Any, r.iloc[0])
    return pd.Series({"opp_key": r["opp_key"], "cus_key": r["cus_key"], "type": r["project_type"], "country": r["country"], "soil_class": r["soil_class"], "route_length_m": r["route_length_m"],
                      "bid_deadline": pd.Timestamp(r["bid_deadline"]) if pd.notna(r["bid_deadline"]) else pd.NaT})


@staged(sources=("crm.opportunity.opp_key", "crm.opportunity.cus_key", "crm.opportunity.carbon_limit_kgco2e_per_m", "crm.opportunity.route_length_m"), oracle="py:tests/test_crm.py::test_story_tenders")
def customer_carbon_limit(opportunity: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the customer carbon limit per route metre of the opportunities that state one.

    Only opportunities with a limit are returned. No bid deadline is given here: ask open_tenders. A limit of zero or less, or a limit on a row without a customer, is refused.

    Args:
        opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, carbon_limit_kgco2e_per_m and route_length_m.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns opp_key, cus_key, carbon_limit_kgco2e_per_m, route_length_m, sorted by opp_key; no rows when no opportunity states a limit.

    Raises:
        FrameError: opportunity is not a DataFrame, lacks a needed column or repeats an opp_key; a carbon limit is zero or below; a carbon limit stands on an opportunity without a customer.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import customer_carbon_limit
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002"], "cus_key": ["CUS-900001", "CUS-900001"],
        ...                     "carbon_limit_kgco2e_per_m": [80.0, None], "route_length_m": [1000.0, 500.0]})
        >>> r = customer_carbon_limit(opp, context=ctx)
        >>> r["opp_key"].tolist(), r["carbon_limit_kgco2e_per_m"].tolist()
        (['OPP-900001'], [80.0])"""
    _need(opportunity, ["opp_key", "cus_key", "carbon_limit_kgco2e_per_m", "route_length_m"], "crm.opportunity", keys=("opp_key",))
    x = opportunity[opportunity["carbon_limit_kgco2e_per_m"].notna()]
    if (x["carbon_limit_kgco2e_per_m"] <= 0).any():
        raise FrameError("a carbon limit must be above zero")
    if x["cus_key"].isna().any():
        raise FrameError("a carbon limit on an opportunity without a customer")
    return x[["opp_key", "cus_key", "carbon_limit_kgco2e_per_m", "route_length_m"]].sort_values("opp_key").reset_index(drop=True)


@staged(sources=("crm.opportunity.opp_key", "crm.opportunity.cus_key", "crm.opportunity.stage", "crm.opportunity.decision_date", "crm.customer.cus_key", "crm.customer.tier",
                 "crm.opportunity_stage_history.opp_key", "crm.opportunity_stage_history.stage", "crm.opportunity_stage_history.entered_date"), oracle="py:tests/test_crm.py::test_funnel_is_plausible")
def win_rate(opportunity: pd.DataFrame, customer: pd.DataFrame, stage_history: pd.DataFrame | None = None, *, freq: str = "year", by_tier: bool = True) -> pd.DataFrame:
    """Use this when you need the win rate (won over decided) by period of the decision date and, if wanted, by customer tier.

    Decided means won plus lost; withdrawn and open opportunities are not decided. Columns: [period,] [tier,] won, lost, decided, win_rate (null with nothing decided), withdrawn. `freq` is year, quarter or month; period is text (such as 2025, 2025-Q3, 2025-03). A period of 'all' is returned with freq None. With the stage history the decision date must equal the date the won or lost stage was entered, else FrameError (a mismatch is a data defect, not rounded away). A decided opportunity without a decision date is refused. A withdrawn opportunity without a decision date has no period and is left out unless freq is None.

    Args:
        opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, stage and decision_date.
        customer: The crm.customer frame, one row per cus_key; it needs cus_key and tier.
        stage_history: Optional crm.opportunity_stage_history frame (opp_key, stage, entered_date) to check the decision date against.
        freq: The period: year, quarter, month or None for one period 'all' (default year).
        by_tier: True to split by customer tier (default), False for the period only.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns period, tier (with by_tier), won, lost, decided, win_rate (rounded to 4 places) and withdrawn, sorted by period and tier.

    Raises:
        FrameError: opportunity, customer or stage_history is not a DataFrame, lacks a needed column or (opportunity, customer) repeats a key; freq is not year, quarter, month or None; a decision date or entered_date is not a date or has a time zone; a won or lost opportunity has no decision date; the decision date differs from the date the decision stage was entered in the stage history; an opportunity belongs to a customer that crm.customer does not hold.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import win_rate
        >>> ctx = Context(stage="month12", role="analyst")
        >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002", "OPP-900003"], "cus_key": ["CUS-900001"] * 3,
        ...                     "stage": ["won", "lost", "withdrawn"], "decision_date": ["2025-03-01", "2025-04-01", "2025-05-01"]})
        >>> cust = pd.DataFrame({"cus_key": ["CUS-900001"], "tier": ["key"]})
        >>> win_rate(opp, cust, by_tier=False, context=ctx).to_dict("records")
        [{'period': '2025', 'won': 1, 'lost': 1, 'decided': 2, 'win_rate': 0.5, 'withdrawn': 1}]"""
    _need(opportunity, ["opp_key", "cus_key", "stage", "decision_date"], "crm.opportunity", keys=("opp_key",))
    _need(customer, ["cus_key", "tier"], "crm.customer", keys=("cus_key",))
    if freq not in ("year", "quarter", "month", None):
        raise FrameError("freq is year, quarter, month or None")
    x = opportunity[opportunity["stage"].isin(["won", "lost", "withdrawn"])].copy()
    dd = _days(x["decision_date"], "decision_date")
    if dd[x["stage"].isin(_DECIDED)].isna().any():
        raise FrameError("a won or lost opportunity has no decision date")
    if freq is not None and dd.isna().any():
        x, dd = x[dd.notna().to_numpy()], dd[dd.notna()]                       # a withdrawn opportunity without a decision date has no period
    if stage_history is not None:
        _need(stage_history, ["opp_key", "stage", "entered_date"], "crm.opportunity_stage_history")
        h = stage_history[stage_history["stage"].isin(["won", "lost", "withdrawn"])].assign(entered=lambda f: _days(f["entered_date"], "entered_date")).drop_duplicates(["opp_key", "stage"], keep="last").set_index("opp_key")
        j = x.assign(_dd=dd).join(h["entered"], on="opp_key")
        if (j["entered"].notna() & (j["entered"] != j["_dd"])).any():
            raise FrameError("the decision date differs from the date the decision stage was entered in the stage history")
    unknown = sorted(set(x["cus_key"].dropna()) - set(customer["cus_key"]))
    if unknown:
        raise FrameError(f"opportunities of customers that crm.customer does not hold, for example {unknown[0]}")
    x = x.assign(tier=x["cus_key"].map(customer.set_index("cus_key")["tier"]))
    if freq == "year":
        x["period"] = dd.dt.strftime("%Y")
    elif freq == "quarter":
        x["period"] = dd.dt.year.astype("Int64").astype(str) + "-Q" + dd.dt.quarter.astype("Int64").astype(str)
    elif freq == "month":
        x["period"] = dd.dt.strftime("%Y-%m")
    else:
        x["period"] = "all"
    keys = ["period"] + (["tier"] if by_tier else [])
    x = x.assign(won=(x["stage"] == "won"), lost=(x["stage"] == "lost"), withdrawn=(x["stage"] == "withdrawn"))
    g = x.groupby(keys, as_index=False, dropna=False, observed=True)[["won", "lost", "withdrawn"]].sum()
    g[["won", "lost", "withdrawn"]] = g[["won", "lost", "withdrawn"]].astype(int)
    g["decided"] = g["won"] + g["lost"]
    g["win_rate"] = (g["won"] / g["decided"].where(g["decided"] > 0)).round(4)
    return g[keys + ["won", "lost", "decided", "win_rate", "withdrawn"]].sort_values(keys).reset_index(drop=True)


@staged(sources=("crm.customer.cus_key", "crm.customer.name", "crm.customer.tier", "projects.project.prj_key", "projects.project.customer_key", "projects.project.status", "projects.project.opp_key",
                 "contracts.contract.con_key", "contracts.contract.cus_key", "contracts.contract.type", "crm.opportunity.opp_key", "crm.opportunity.expected_value_dkk", "crm.opportunity.stage"),
        oracle="py:tests/test_crm.py::test_customers_and_anchors")
def customer_projects(customer: pd.DataFrame, project: pd.DataFrame, contract: pd.DataFrame, opportunity: pd.DataFrame | None = None, *, by: str = "customer",
                      contract_types: Sequence[str] = ("customer_project", "customer_framework", "customer_service")) -> pd.DataFrame:
    """Use this when you need the projects and contracts per customer, or the totals and shares per customer tier.

    Customer rows (by='customer'): cus_key, name, tier, n_projects, n_active, n_contracts (contracts of `contract_types`, PROPOSED the three customer types) and, with `opportunity`, won_value_dkk (expected_value_dkk of the won opportunities of the customer, not converted here). Tier rows (by='tier'): tier, n_customers, n_projects, n_contracts, won_value_dkk (with opportunity), share_of_projects and share_of_won_value (with opportunity; of all customers). Customers without a project are listed with zero.

    Args:
        customer: The crm.customer frame, one row per cus_key; it needs cus_key, name and tier (no nulls).
        project: The projects.project frame, one row per prj_key; it needs prj_key, customer_key (no nulls) and status.
        contract: The contracts.contract frame, one row per con_key; it needs con_key, cus_key and type.
        opportunity: Optional crm.opportunity frame, one row per opp_key (opp_key, cus_key, stage, expected_value_dkk); it adds the won value.
        by: customer for one row per customer (default) or tier for one row per tier.
        contract_types: The contract types that count as customer contracts, a tuple or list, not a text (default customer_project, customer_framework, customer_service; PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame sorted by cus_key (by customer) or in the tier order anchor, key, standard, occasional, then other tiers (by tier); the columns are those named above.

    Raises:
        FrameError: a frame is not a DataFrame, lacks a needed column or repeats a key (customer by cus_key, project by prj_key, contract by con_key, opportunity by opp_key); by is not customer or tier; contract_types is a text instead of a list; a project has no customer_key or a customer has no tier; a project or a won opportunity belongs to a customer that crm.customer does not hold.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import customer_projects
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cust = pd.DataFrame({"cus_key": ["CUS-900001", "CUS-900002"], "name": ["Customer A", "Customer B"], "tier": ["key", "standard"]})
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "customer_key": ["CUS-900001"], "status": ["active"]})
        >>> con = pd.DataFrame({"con_key": ["CON-900001"], "cus_key": ["CUS-900001"], "type": ["customer_project"]})
        >>> customer_projects(cust, prj, con, context=ctx)[["cus_key", "n_projects", "n_active", "n_contracts"]].to_dict("records")
        [{'cus_key': 'CUS-900001', 'n_projects': 1, 'n_active': 1, 'n_contracts': 1}, {'cus_key': 'CUS-900002', 'n_projects': 0, 'n_active': 0, 'n_contracts': 0}]"""
    _need(customer, ["cus_key", "name", "tier"], "crm.customer", keys=("cus_key",))
    _need(project, ["prj_key", "customer_key", "status"], "projects.project", keys=("prj_key",))
    _need(contract, ["con_key", "cus_key", "type"], "contracts.contract", keys=("con_key",))
    if by not in ("customer", "tier"):
        raise FrameError("by is customer or tier")
    types = _strs(contract_types, "contract_types")
    if project["customer_key"].isna().any() or customer["tier"].isna().any():
        raise FrameError("a project without a customer_key or a customer without a tier cannot be placed in a tier share")
    unknown = sorted(set(project["customer_key"].dropna()) - set(customer["cus_key"]))
    if unknown:
        raise FrameError(f"projects of customers that crm.customer does not hold, for example {unknown[0]}")
    c = customer[["cus_key", "name", "tier"]].astype({"tier": object, "cus_key": object}).copy()
    c["n_projects"] = c["cus_key"].map(project.groupby("customer_key").size()).fillna(0).astype(int)
    c["n_active"] = c["cus_key"].map(project[project["status"] == "active"].groupby("customer_key").size()).fillna(0).astype(int)
    c["n_contracts"] = c["cus_key"].map(contract[contract["type"].isin(types)].groupby("cus_key").size()).fillna(0).astype(int)
    if opportunity is not None:
        _need(opportunity, ["opp_key", "cus_key", "stage", "expected_value_dkk"], "crm.opportunity", keys=("opp_key",))
        won = opportunity[opportunity["stage"] == "won"]
        if not set(won["cus_key"].dropna()) <= set(customer["cus_key"]):
            raise FrameError("won opportunities of customers that crm.customer does not hold")
        c["won_value_dkk"] = c["cus_key"].map(won.groupby("cus_key")["expected_value_dkk"].sum()).fillna(0.0)
    c = c.sort_values("cus_key").reset_index(drop=True)
    if by == "customer":
        return c
    agg = {"n_customers": ("cus_key", "size"), "n_projects": ("n_projects", "sum"), "n_contracts": ("n_contracts", "sum")}
    if "won_value_dkk" in c:
        agg["won_value_dkk"] = ("won_value_dkk", "sum")
    t = c.groupby("tier", as_index=False, observed=True).agg(**agg)
    t["share_of_projects"] = (t["n_projects"] / t["n_projects"].sum()).round(4) if t["n_projects"].sum() else np.nan
    if "won_value_dkk" in t:
        t["share_of_won_value"] = (t["won_value_dkk"] / t["won_value_dkk"].sum()).round(4) if t["won_value_dkk"].sum() else np.nan
    order = {k: i for i, k in enumerate(_TIER_ORDER)}
    return t.assign(_o=t["tier"].map(order).fillna(len(order))).sort_values(["_o", "tier"]).drop(columns="_o").reset_index(drop=True)
