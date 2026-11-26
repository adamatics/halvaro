"""Customer sustainability requests (plan 5.8, module `requests` of the plan, named data_requests here because the scaffold test bans an import called requests): status from dates, the limit of a tender cross-checked against the crm side, the numbers a questionnaire needs, and the time to answer.

The snapshot `status` column is never trusted: the status is derived from received, due and answered dates as of a day. A mismatch with the crm side is reported, never corrected.
"""
from __future__ import annotations

from typing import Any, NamedTuple, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _day, _need
from ._types import DateLike

_R = tuple(f"energy-esg.esg_data_request.{c}" for c in ("cus_key", "request_no", "received", "due", "answered_date", "status", "request_type", "opp_key", "limit_kgco2e_per_m"))


def _dates(R: pd.DataFrame, cols: Sequence[str] = ("received", "due", "answered_date")) -> pd.DataFrame:
    _need(R, ["cus_key", "request_no", *cols], "energy-esg.esg_data_request")
    if R.duplicated(["cus_key", "request_no"]).any():
        raise FrameError("energy-esg.esg_data_request has more than one row for a customer and request number")
    out = R.copy()
    for c in cols:
        nn = R[c].dropna()
        if len(nn) and (pd.api.types.is_numeric_dtype(R[c]) or any(isinstance(v, (bool, int, float, np.number)) for v in nn)):
            raise FrameError(f"energy-esg.esg_data_request.{c} holds numbers, not dates")
        try:
            out[c] = pd.to_datetime(R[c]).dt.normalize()
        except (ValueError, TypeError, OverflowError) as e:
            raise FrameError(f"energy-esg.esg_data_request.{c} holds a value that is not a date: {e}") from None
    if out["received"].isna().any() or out["due"].isna().any():
        raise FrameError("energy-esg.esg_data_request needs a received and a due date on every row")
    if (out["due"] < out["received"]).any():
        raise FrameError("energy-esg.esg_data_request has a request due before it was received")
    return out


@staged(sources=_R, oracle="py:tests/test_energy_esg.py::test_customer_data_requests")
def open_requests(R: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the status of every customer sustainability request on a given day, worked out from its dates.

    The status of every request on a day, from its dates and not from the snapshot `status`: not_received (received after the day), answered (answered on or before the day), overdue (due before
    the day and not answered), open (received, due on or after the day, not answered). The stored status is informative only: the snapshot is as of the release; a stored 'open' for a request that is overdue as of the day is a difference, not hidden.

    Args:
        R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due and answered_date, and optionally request_type and status.
        as_of: The day (a date, Timestamp, ISO text or YYYY-MM) as of which the status is derived.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns cus_key, request_no, request_type, received, due, answered_date (as of the day: null when answered later), status_as_of, days_to_due (due less the day; negative when overdue), and, when R has a status column, stored_status and status_agrees (the derived status against the snapshot), sorted by cus_key and request_no.

    Raises:
        FrameError: R is not a frame or lacks a needed column; R has two rows for a customer and request number.
        FrameError: received, due or answered_date holds numbers or a value that is not a date; a row has no received or due date; a request is due before it was received.
        FrameError: as_of is a number, not a date, or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import open_requests
        >>> ctx = Context(stage="month12", role="analyst")
        >>> R = pd.DataFrame({
        ...     "cus_key": ["CUS-900001", "CUS-900001", "CUS-900002"], "request_no": [1, 2, 1],
        ...     "received": ["2031-03-01", "2031-03-10", "2031-04-20"], "due": ["2031-03-31", "2031-04-10", "2031-05-20"],
        ...     "answered_date": ["2031-03-20", None, None], "status": ["answered", "open", "open"]})
        >>> out = open_requests(R, "2031-04-15", context=ctx)
        >>> out[["cus_key", "request_no", "status_as_of", "days_to_due", "status_agrees"]].values.tolist()
        [['CUS-900001', 1, 'answered', -15, True], ['CUS-900001', 2, 'overdue', -5, False], ['CUS-900002', 1, 'not_received', 35, False]]
    """
    d = _day(as_of, "as_of")
    x = _dates(R)
    ans = x["answered_date"].where(x["answered_date"] <= d)
    st = np.select([x["received"] > d, ans.notna(), x["due"] < d], ["not_received", "answered", "overdue"], default="open")
    out = pd.DataFrame({"cus_key": x["cus_key"], "request_no": x["request_no"], "request_type": x["request_type"] if "request_type" in x else None, "received": x["received"], "due": x["due"],
                        "answered_date": ans, "status_as_of": st, "days_to_due": (x["due"] - d).dt.days})
    if "status" in x:
        out["stored_status"] = x["status"]
        out["status_agrees"] = out["status_as_of"] == x["status"]
    return out.sort_values(["cus_key", "request_no"]).reset_index(drop=True)


class TenderLimit(NamedTuple):
    """The tender request row, the limit and due date it states, and the cross-check: `crm_limit` and `bid_deadline` from the crm side (null when not given), `limit_agrees` and `due_agrees` (null when not checked)."""
    cus_key: str
    request_no: int
    opp_key: str
    limit_kgco2e_per_m: float
    due: pd.Timestamp
    crm_limit: float
    limit_agrees: object
    bid_deadline: object
    due_agrees: object
    warnings: tuple[str, ...]


@staged(sources=(*_R, "crm.opportunity.carbon_limit_kgco2e_per_m", "crm.opportunity.bid_deadline"), oracle="py:tests/test_energy_esg.py::test_customer_data_requests")
def tender_limit(R: pd.DataFrame, CL: pd.DataFrame | None = None, OT: pd.DataFrame | None = None, *, request_type: str = "tender_requirement") -> list[TenderLimit]:
    """Use this when you need the carbon limit and due date of each tender requirement, checked against the crm side.

    The tender requirement rows of R (request_type 'tender_requirement', PROPOSED) as TenderLimit. `CL` is the delivery customer_carbon_limit frame (opp_key and limit_kgco2e_per_m or
    carbon_limit_kgco2e_per_m), `OT` the delivery open_tenders frame (opp_key, bid_deadline). A limit or a due date that differs from the crm side is reported in `warnings` and never corrected; without CL or
    OT the row is returned with a warning that it was not cross-checked. A tender row without an opp_key or a limit raises FrameError.

    Args:
        R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due, answered_date, request_type, opp_key and limit_kgco2e_per_m.
        CL: The delivery customer_carbon_limit frame with opp_key (one row per opportunity) and limit_kgco2e_per_m or carbon_limit_kgco2e_per_m, and optionally cus_key; None to skip that check.
        OT: The delivery open_tenders frame with opp_key (one row per opportunity) and bid_deadline; None to skip that check.
        request_type: The request_type that marks a tender requirement (PROPOSED: tender_requirement).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A list of TenderLimit tuples, one per tender row of R in the order of R, with cus_key, request_no, opp_key, limit_kgco2e_per_m, due, crm_limit and bid_deadline (null when the crm side gives none), limit_agrees and due_agrees (null when not checked) and warnings (a tuple of texts, empty when everything agrees); empty when R has no tender row.

    Raises:
        FrameError: R is not a frame or lacks a needed column (including request_type, opp_key and limit_kgco2e_per_m); R has two rows for a customer and request number; a date column holds numbers, a value that is not a date, no received or due date, or a due date before the received date.
        FrameError: a tender row has no opp_key or no limit.
        FrameError: CL lacks opp_key or both limit columns, or OT lacks opp_key or bid_deadline; CL or OT has more than one row for an opportunity.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import tender_limit
        >>> ctx = Context(stage="month12", role="analyst")
        >>> R = pd.DataFrame({
        ...     "cus_key": ["CUS-900001"], "request_no": [2], "received": ["2031-03-10"], "due": ["2031-04-10"], "answered_date": [None],
        ...     "request_type": ["tender_requirement"], "opp_key": ["OPP-900001"], "limit_kgco2e_per_m": [12.5]})
        >>> CL = pd.DataFrame({"opp_key": ["OPP-900001"], "limit_kgco2e_per_m": [12.5]})
        >>> OT = pd.DataFrame({"opp_key": ["OPP-900001"], "bid_deadline": ["2031-04-10"]})
        >>> t = tender_limit(R, CL, OT, context=ctx)
        >>> [(x.opp_key, x.limit_kgco2e_per_m, x.limit_agrees, x.due_agrees, x.warnings) for x in t]
        [('OPP-900001', 12.5, True, True, ())]
        >>> tender_limit(R, context=ctx)[0].warnings
        ('not cross-checked against the crm side',)
    """
    x = _dates(R)
    _need(x, ["request_type", "opp_key", "limit_kgco2e_per_m"], "energy-esg.esg_data_request")
    t = x[x["request_type"] == request_type]
    if t["opp_key"].isna().any() or t["limit_kgco2e_per_m"].isna().any():
        raise FrameError("a tender requirement needs an opp_key and a limit")
    cl = cus = None
    if CL is not None:
        _need(CL, ["opp_key"], "customer_carbon_limit frame")
        lc = "limit_kgco2e_per_m" if "limit_kgco2e_per_m" in CL.columns else "carbon_limit_kgco2e_per_m"
        _need(CL, [lc], "customer_carbon_limit frame")
        if CL["opp_key"].duplicated().any():
            raise FrameError("the customer_carbon_limit frame has more than one row for an opportunity")
        cl = CL.set_index("opp_key")[lc]
        cus = CL.set_index("opp_key")["cus_key"] if "cus_key" in CL.columns else None
    ot = None
    if OT is not None:
        _need(OT, ["opp_key", "bid_deadline"], "open_tenders frame")
        if OT["opp_key"].duplicated().any():
            raise FrameError("the open_tenders frame has more than one row for an opportunity")
        ot = pd.to_datetime(OT.set_index("opp_key")["bid_deadline"]).dt.normalize()
    out = []
    r: Any
    for r in t.itertuples():
        w, crm, la, bd, da = [], np.nan, None, None, None
        if cl is None and ot is None:
            w.append("not cross-checked against the crm side")
        elif cl is None or ot is None:
            w.append("partly cross-checked: " + ("limit only" if ot is None else "bid deadline only"))
        if cl is not None:
            if r.opp_key in cl.index:
                crm = float(cl.loc[r.opp_key])
                if cus is not None and cus.loc[r.opp_key] != r.cus_key:
                    w.append(f"customer {r.cus_key} differs from the crm customer {cus.loc[r.opp_key]}")
                la = bool(abs(crm - float(r.limit_kgco2e_per_m)) < 1e-9)
                if not la:
                    w.append(f"limit {r.limit_kgco2e_per_m} differs from the crm limit {crm}")
            else:
                w.append("the opportunity has no limit on the crm side")
        if ot is not None:
            if r.opp_key in ot.index:
                bd = ot.loc[r.opp_key]
                da = None if pd.isna(bd) else bool(bd == r.due)
                if da is None:
                    w.append("the bid deadline on the crm side is missing")
                elif not da:
                    w.append(f"due {r.due.date()} differs from the bid deadline {bd.date()}")
            else:
                w.append("the opportunity is not an open tender")
        out.append(TenderLimit(r.cus_key, int(r.request_no), r.opp_key, float(r.limit_kgco2e_per_m), r.due, crm, la, bd, da, tuple(w)))
    return out


@staged(sources=("energy-esg.emission_line.kgco2e", "energy-esg.target.target_no"), oracle="py:tests/test_oracle_data_requests.py::test_oracle_answer_pack_every_route")
def answer_pack(req: pd.DataFrame, totals: pd.DataFrame, targets: pd.DataFrame) -> dict[str, Any]:
    """Use this when you need the numbers to answer a customer questionnaire: the scope totals, the months covered, the targets and the notes.

    The numbers a questionnaire needs, no document text: for the request row `req` (one row) the scope totals `totals` (the output of scope_totals, one entity row 'ALL' and a year), both scope 2
    methods side by side and never added, the months covered, the restatement note when the totals are on the current basis, and the targets with their basis. The two scope 2 values are never summed.

    Args:
        req: One row of the request with the columns cus_key and request_no.
        totals: One row of scope_totals for the entity 'ALL' (le_key, when present, must be 'ALL') with the columns year, months, scope1, scope2_location, scope2_market and scope3, and optionally basis; none of months and the scope values may be null.
        targets: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, reduction_percent, basis and status.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A dict with the keys request (cus_key and request_no as a tuple), year, months, scope1, scope2_location, scope2_market, scope3 (floats), targets (the target rows as a list of dicts, sorted by target_no) and notes (a list of texts: the basis of the totals, that scope 2 is given by both methods and not added, that the emission factors are synthetic, and the number of months when the year has fewer than 12).

    Raises:
        FrameError: req, totals or targets lacks a needed column.
        FrameError: req or totals does not have exactly one row; totals is not the whole company (le_key other than 'ALL'); year, months or a scope value in totals is null.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import answer_pack
        >>> ctx = Context(stage="month12", role="analyst")
        >>> req = pd.DataFrame({"cus_key": ["CUS-900001"], "request_no": [1]})
        >>> totals = pd.DataFrame({"le_key": ["ALL"], "year": [2031], "months": [12], "scope1": [100.0], "scope2_location": [50.0],
        ...                        "scope2_market": [20.0], "scope3": [300.0], "basis": ["current"]})
        >>> targets = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2029], "target_year": [2035],
        ...                         "reduction_percent": [40.0], "basis": ["absolute"], "status": ["proposed"]})
        >>> pack = answer_pack(req, totals, targets, context=ctx)
        >>> pack["request"], pack["scope2_location"], pack["scope2_market"]
        (('CUS-900001', 1), 50.0, 20.0)
        >>> pack["notes"][0]
        'totals are on the current basis: earlier years may have been restated'
    """
    _need(req, ["cus_key", "request_no"], "the request row")
    _need(totals, ["year", "months", "scope1", "scope2_location", "scope2_market", "scope3"], "the scope totals")
    _need(targets, ["target_no", "scope", "baseline_year", "target_year", "reduction_percent", "basis", "status"], "energy-esg.target")
    if len(req) != 1 or len(totals) != 1:
        raise FrameError("answer_pack takes one request row and one totals row")
    t = totals.iloc[0]
    if "le_key" in totals.columns and totals["le_key"].iloc[0] != "ALL":
        raise FrameError("answer_pack takes the totals of the whole company (le_key 'ALL'), not one entity")
    if totals[["year", "months", "scope1", "scope2_location", "scope2_market", "scope3"]].isna().any().any():
        raise FrameError("the scope totals have nulls")
    basis = str(t["basis"]) if "basis" in totals.columns else "unknown"
    notes = [f"totals are on the {basis} basis" + (": earlier years may have been restated" if basis == "current" else ""), "scope 2 is given by both methods and the two are not added", "emission factors are synthetic: not for real reporting"]
    if int(t["months"]) < 12:
        notes.append(f"the year has {int(t['months'])} months of data")
    return {"request": (req["cus_key"].iloc[0], int(req["request_no"].iloc[0])), "year": int(t["year"]), "months": int(t["months"]), "scope1": float(t["scope1"]), "scope2_location": float(t["scope2_location"]),
            "scope2_market": float(t["scope2_market"]), "scope3": float(t["scope3"]), "targets": targets.sort_values("target_no").to_dict("records"), "notes": notes}


@staged(sources=_R, oracle="py:tests/test_oracle_data_requests.py::test_oracle_request_timeliness_every_route")
def request_timeliness(R: pd.DataFrame, *, as_of: DateLike | None = None) -> pd.DataFrame:
    """Use this when you need how many days customer requests take to be answered and how many are answered by the due date, per request type.

    Days from receipt to answer and whether the answer came by the due date, by request type. Requests not answered are counted in n and not in the shares. With `as_of`, answers after that day count as not answered.

    Args:
        R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due, answered_date and request_type.
        as_of: A day (date, Timestamp or ISO text) after which answers do not count and requests received after it are left out; None to use every answer.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns request_type, n, n_answered, mean_days_to_answer, median_days_to_answer (rounded to 2 decimals), n_on_time and share_on_time (n_on_time over n_answered, rounded to 4 decimals; null when none is answered), sorted by request_type.

    Raises:
        FrameError: R is not a frame or lacks a needed column; R has two rows for a customer and request number; a date column holds numbers, a value that is not a date, no received or due date, or a due date before the received date.
        FrameError: a request has no request_type; a request was answered before it was received.
        FrameError: as_of is a number, not a date, or has a time zone.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import request_timeliness
        >>> ctx = Context(stage="month12", role="analyst")
        >>> R = pd.DataFrame({
        ...     "cus_key": ["CUS-900001", "CUS-900001", "CUS-900002"], "request_no": [1, 2, 1],
        ...     "received": ["2031-03-01", "2031-03-10", "2031-04-20"], "due": ["2031-03-31", "2031-04-10", "2031-05-20"],
        ...     "answered_date": ["2031-03-20", "2031-04-15", None],
        ...     "request_type": ["questionnaire", "questionnaire", "tender_requirement"]})
        >>> out = request_timeliness(R, context=ctx)
        >>> out[["request_type", "n", "n_answered", "n_on_time", "share_on_time"]].values.tolist()
        [['questionnaire', 2, 2, 1, 0.5], ['tender_requirement', 1, 0, 0, nan]]
    """
    x = _dates(R)
    _need(x, ["request_type"], "energy-esg.esg_data_request")
    if x["request_type"].isna().any():
        raise FrameError("energy-esg.esg_data_request has a request without a request_type")
    if as_of is not None:
        d = _day(as_of, "as_of")
        x = x[x["received"] <= d].assign(answered_date=lambda f: f["answered_date"].where(f["answered_date"] <= d))
    if (x["answered_date"] < x["received"]).any():
        raise FrameError("energy-esg.esg_data_request has a request answered before it was received")
    x = x.assign(days=(x["answered_date"] - x["received"]).dt.days, on_time=(x["answered_date"] <= x["due"]) & x["answered_date"].notna())
    g = x.groupby("request_type", as_index=False).agg(n=("request_no", "size"), n_answered=("answered_date", "count"), mean_days_to_answer=("days", "mean"), median_days_to_answer=("days", "median"), n_on_time=("on_time", "sum"))
    g["share_on_time"] = (g["n_on_time"] / g["n_answered"].where(g["n_answered"] > 0)).round(4)
    g[["mean_days_to_answer", "median_days_to_answer"]] = g[["mean_days_to_answer", "median_days_to_answer"]].round(2)
    return g.sort_values("request_type").reset_index(drop=True)
