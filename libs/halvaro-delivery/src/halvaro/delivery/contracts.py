"""Contracts: the framework of a supplier on a date, the contracts of a project, clauses on a date, price adjustment terms by parameter name, notification hours, obligations on a date and legal flags (plan 5.7).

Parameters of a clause are read by name, never by position: pass_through_percent is `param_name` and threshold_percent is `param2_name` of the price clause (3.4). Legal values are facts with their status.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import AmbiguousKey, FrameError, combine_status, fact, rows_on

from ._guard import staged
from ._types import DateLike

_KB = ("DA.REF.216",)
_CLAUSE = ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to", "verify", "legal_note"]
_CLAUSE_SRC = tuple(f"contracts.clause.{c}" for c in _CLAUSE)
_CONTRACT = ["con_key", "type", "cus_key", "sup_key", "prj_key", "parent_con_key", "price_type", "status", "start", "end", "legal_entity_key"]
_ORACLE = "py:tests/test_contracts.py::test_clauses_are_clean"
_WARRANTY = {"DK": "legal.contracts.warranty_years.DK", "DE": "legal.contracts.warranty_years.DE"}
_KEPT_STATUS = ("waived", "breached", "in_force", "closed")      # stored statuses the dates cannot derive
_NOT_IN_FORCE = ("draft", "awaiting_signature", "signed")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str, keys: Sequence[str] = ()) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise FrameError(f"{what} must be a DataFrame, not {type(frame).__name__}")
    if frame.columns.duplicated().any():
        raise FrameError(f"{what} has duplicate column names")
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} lacks column(s) {', '.join(missing)}; load the source columns without renaming them")
    if keys and frame.duplicated(list(keys)).any():
        d = frame[frame.duplicated(list(keys), keep=False)].iloc[0]
        raise FrameError(f"{what} has more than one row for {', '.join(str(d[k]) for k in keys)}; one row per key is required")


def _dates(frame: pd.DataFrame, columns: Sequence[str], what: str) -> pd.DataFrame:
    out = frame.copy()
    for c in columns:
        try:
            out[c] = pd.to_datetime(out[c]).dt.normalize()
        except (ValueError, TypeError, OverflowError, AttributeError) as e:
            raise FrameError(f"{what}.{c} holds a value that is not a date: {e}") from None
    return out


def _day(as_of: Any) -> pd.Timestamp:
    if isinstance(as_of, (bool, int, float, np.number)):
        raise FrameError(f"as_of {as_of!r} is a number, not a date")
    try:
        d = pd.Timestamp(as_of)
    except (ValueError, TypeError, OverflowError) as e:
        raise FrameError(f"as_of {as_of!r} is not a date: {e}") from None
    if pd.isna(d) or d.tzinfo is not None:
        raise FrameError(f"as_of {as_of!r} is not a date without a time zone")
    return d.normalize()


@staged(sources=tuple(f"contracts.contract.{c}" for c in ("con_key", "type", "sup_key", "status", "start", "end")), kb=_KB, oracle="py:tests/test_contracts.py::test_supplier_frameworks")
def framework_for(contract: pd.DataFrame, sup_key: str, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the supplier framework contract that is in force for a supplier on a date.

    The framework is the contracts.contract row of type supplier_framework for the supplier that has started on or before the date (start) and has not ended before it (end null or on or after it). A draft, a contract awaiting signature and a signed one that has not started are not frameworks in force. There is at most one row; an empty frame means the supplier has no framework on the date.

    Args:
        contract: The contracts.contract frame, one row per con_key; it needs con_key, type, sup_key, status, start and end.
        sup_key: The supplier key as text, for example SUP-900001.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns of the contract frame, holding the one valid framework row (index reset), or no rows when there is none.

    Raises:
        FrameError: contract is not a DataFrame, has duplicate column names, lacks a needed column or repeats a con_key; sup_key is not text; as_of is a number, has a time zone or is not a date; start or end holds a value that is not a date.
        AmbiguousKey: two frameworks of the supplier are valid on the date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import framework_for
        >>> ctx = Context(stage="month12", role="analyst")
        >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "type": ["supplier_framework", "supplier_framework"],
        ...                     "sup_key": ["SUP-900001", "SUP-900001"], "status": ["in_force", "draft"],
        ...                     "start": ["2025-01-01", "2025-01-01"], "end": [None, None]})
        >>> framework_for(con, "SUP-900001", "2026-03-01", context=ctx)["con_key"].tolist()
        ['CON-900001']"""
    _need(contract, ["con_key", "type", "sup_key", "status", "start", "end"], "contracts.contract", keys=("con_key",))
    d = _day(as_of)
    if not isinstance(sup_key, str):
        raise FrameError(f"sup_key is one key as text, not {type(sup_key).__name__}")
    c = _dates(contract[(contract["type"] == "supplier_framework") & (contract["sup_key"] == sup_key) & ~contract["status"].isin(_NOT_IN_FORCE)], ["start", "end"], "contracts.contract")
    hit = c[(c["start"] <= d) & (c["end"].isna() | (c["end"] >= d))]
    if len(hit) > 1:
        raise AmbiguousKey(sup_key, sorted(hit["con_key"]))
    return hit.reset_index(drop=True)


@staged(sources=("projects.project.prj_key", "projects.project.contract_key", "contracts.contract.con_key", "contracts.contract.parent_con_key", "contracts.contract.type",
                 "procurement.purchase_order.prj_key", "procurement.purchase_order.con_key"), kb=_KB, oracle="py:tests/test_contracts.py::test_project_contracts_resolve")
def contracts_for_project(project: pd.DataFrame, contract: pd.DataFrame, purchase_order: pd.DataFrame, prj_key: str) -> pd.DataFrame:
    """Use this when you need every contract that touches one project: its customer contract, the parent frameworks above it and the supplier frameworks of its purchase orders.

    The contracts are: the customer contract of the project (kind customer_contract), the parent contract of a call-off (parent_framework, followed up the chain), and the supplier frameworks of the project's purchase orders (supplier_framework, with the number of orders; an order that points at another type of contract is listed as other_contract). Columns: kind, con_key, type, sup_key, cus_key, orders. Sorted by kind and con_key. An unknown project raises.

    Args:
        project: The projects.project frame, one row per prj_key; it needs prj_key and contract_key.
        contract: The contracts.contract frame, one row per con_key; it needs con_key, type, sup_key, cus_key and parent_con_key.
        purchase_order: The procurement.purchase_order frame; it needs prj_key and con_key.
        prj_key: The project key as listed in the project frame, for example PRJ-900001.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with kind, con_key, type, sup_key, cus_key and orders (the number of orders of that contract for the project; 0 for the customer contract and its parents), sorted by kind and con_key, index reset.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names, lacks a needed column, or repeats a prj_key or con_key where one row per key is required; the project is not in the project frame exactly once; its contract, a parent contract or the framework of an order is not in contracts.contract; the parent chain loops.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import contracts_for_project
        >>> ctx = Context(stage="month12", role="analyst")
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "contract_key": ["CON-900001"]})
        >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002", "CON-900003"],
        ...                     "type": ["customer_project", "customer_framework", "supplier_framework"],
        ...                     "sup_key": [None, None, "SUP-900001"], "cus_key": ["CUS-900001", "CUS-900001", None],
        ...                     "parent_con_key": ["CON-900002", None, None]})
        >>> po = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "con_key": ["CON-900003", "CON-900003"]})
        >>> out = contracts_for_project(prj, con, po, "PRJ-900001", context=ctx)
        >>> out[["kind", "con_key", "orders"]].values.tolist()
        [['customer_contract', 'CON-900001', 0], ['parent_framework', 'CON-900002', 0], ['supplier_framework', 'CON-900003', 2]]"""
    _need(project, ["prj_key", "contract_key"], "projects.project", keys=("prj_key",))
    _need(contract, ["con_key", "type", "sup_key", "cus_key", "parent_con_key"], "contracts.contract", keys=("con_key",))
    _need(purchase_order, ["prj_key", "con_key"], "procurement.purchase_order")
    p = project[project["prj_key"] == prj_key]
    if len(p) != 1:
        raise FrameError(f"project {prj_key} is not in the project frame exactly once")
    ct = contract.set_index("con_key")
    rows = []
    own = p["contract_key"].iloc[0]
    if pd.notna(own):
        if own not in ct.index:
            raise FrameError(f"the contract {own} of {prj_key} is not in contracts.contract")
        rows.append(("customer_contract", own, 0))
        seen, cur = {own}, ct.loc[own, "parent_con_key"]
        while pd.notna(cur):
            if cur in seen:
                raise FrameError(f"the parent chain of {own} loops at {cur}")
            if cur not in ct.index:
                raise FrameError(f"the parent contract {cur} of {own} is not in contracts.contract")
            rows.append(("parent_framework", cur, 0))
            seen.add(cur)
            cur = ct.loc[cur, "parent_con_key"]
    po = purchase_order[(purchase_order["prj_key"] == prj_key) & purchase_order["con_key"].notna()].groupby("con_key").size()
    listed = {r[1] for r in rows}
    for k, n in po.items():
        if k not in ct.index:
            raise FrameError(f"the framework {k} of an order of {prj_key} is not in contracts.contract")
        rows.append(("supplier_framework" if cast(Any, ct.loc)[k, "type"] == "supplier_framework" and k not in listed else "other_contract", k, int(n)))
    out = pd.DataFrame(rows, columns=["kind", "con_key", "orders"])
    out = out.merge(contract[["con_key", "type", "sup_key", "cus_key"]], on="con_key", how="left")
    return out[["kind", "con_key", "type", "sup_key", "cus_key", "orders"]].sort_values(["kind", "con_key"]).reset_index(drop=True)


def _clauses_on(clause: pd.DataFrame, as_of: Any, con_key: str | None = None, clause_type: str | None = None) -> pd.DataFrame:
    _need(clause, ["con_key", "clause_no", "clause_type", "valid_from", "valid_to"], "contracts.clause")
    for name, v in (("con_key", con_key), ("clause_type", clause_type)):
        if v is not None and not isinstance(v, str):
            raise FrameError(f"{name} is one value as text, not {type(v).__name__}")
    c = _dates(clause, ["valid_from", "valid_to"], "contracts.clause")
    if con_key is not None:
        c = c[c["con_key"] == con_key]
    if clause_type is not None:
        c = c[c["clause_type"] == clause_type]
    d = _day(as_of)
    out = c[(c["valid_from"] <= d) & (c["valid_to"].isna() | (c["valid_to"] >= d))]
    return out.sort_values(["con_key", "clause_no"]).reset_index(drop=True)


@staged(sources=_CLAUSE_SRC, kb=_KB, oracle=_ORACLE)
def clauses_on(clause: pd.DataFrame, as_of: DateLike, *, con_key: str | None = None, clause_type: str | None = None) -> pd.DataFrame:
    """Use this when you need the contract clauses that are valid on a date, optionally for one contract and one clause type.

    A clause is valid on the date by its own valid_from (on or before it) and valid_to (null or on or after it). Every column of contracts.clause is kept (including qual_key for the qualification clauses). The clauses of every contract are returned, also those of a contract that has ended or has not started (the contract frame is not read here). Filter with the contract frame (framework_for, start and end) when only contracts in force matter.

    Args:
        clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, variant, param_name, param_value, param2_name, param2_value, valid_from, valid_to, verify and legal_note.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        con_key: Optional keyword, one contract key as text; only its clauses are returned.
        clause_type: Optional keyword, one clause type as text; only clauses of that type are returned.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with every column of the clause frame, the valid clauses sorted by con_key and clause_no, index reset.

    Raises:
        FrameError: clause is not a DataFrame, has duplicate column names or lacks a needed column; con_key or clause_type is not text; valid_from or valid_to holds a value that is not a date; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import clauses_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to", "verify", "legal_note"]
        >>> rows = [["CON-900001", 1, "warranty", "works", "warranty_years", 5.0, None, None, "2025-01-01", None, False, None],
        ...         ["CON-900001", 2, "notification", "std", "notification_hours", 24.0, None, None, "2024-01-01", "2024-12-31", False, None]]
        >>> clause = pd.DataFrame(rows, columns=cols)
        >>> clauses_on(clause, "2025-06-01", context=ctx)["clause_no"].tolist()
        [1]
        >>> clauses_on(clause, "2024-06-01", con_key="CON-900001", clause_type="notification", context=ctx)["clause_no"].tolist()
        [2]"""
    return _clauses_on(clause, as_of, con_key, clause_type)


class PriceTerms(NamedTuple):
    """Result of price_adjustment_terms: one row per price clause, and the customer project contracts that have none."""

    terms: pd.DataFrame
    without_clause: pd.DataFrame


@staged(sources=_CLAUSE_SRC + ("contracts.contract.type", "contracts.contract.price_type"), kb=_KB, oracle="py:tests/test_contracts.py::test_price_revision_nordvolt")
def price_adjustment_terms(clause: pd.DataFrame, contract: pd.DataFrame, as_of: DateLike | None = None) -> PriceTerms:
    """Use this when you need the price adjustment terms of the contracts (pass-through percent and threshold percent) and the customer project contracts that have no price clause.

    The price adjustment clauses are returned with their parameters read by name: variant, pass_through_percent (the clause parameter of that name, `param_name`) and threshold_percent (`param2_name`), the first parameter and the second as they are, and n_price_clauses of the contract (a supplier contract can have several, a customer contract one). Customer project contracts with no price clause are returned in `without_clause` (the generator test cannot see them). With as_of only clauses valid on the date. The threshold is returned and applied nowhere (policy.pricing.pass_through_threshold_is_deductible, proposed).

    Args:
        clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, variant, param_name, param_value, param2_name, param2_value, valid_from and valid_to.
        contract: The contracts.contract frame, one row per con_key; it needs con_key, type and price_type.
        as_of: Optional day (a date, a Timestamp or an ISO text); when given, only clauses valid on it are used. None (the default) uses all price clauses.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A PriceTerms named tuple. `terms` has con_key, clause_no, variant, param_name, param_value, param2_name, param2_value, valid_from, valid_to, pass_through_percent, threshold_percent, n_price_clauses, type and price_type, sorted by con_key and clause_no. `without_clause` has con_key, type and price_type of the customer_project contracts with no price clause.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract frame repeats a con_key; valid_from or valid_to holds a value that is not a date; as_of (when given) is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import price_adjustment_terms
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to"]
        >>> clause = pd.DataFrame([["CON-900001", 1, "price_adjustment", "index", "pass_through_percent", 80.0, "threshold_percent", 2.0, "2025-01-01", None]], columns=cols)
        >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "type": ["customer_project", "customer_project"], "price_type": ["fixed", "fixed"]})
        >>> res = price_adjustment_terms(clause, con, context=ctx)
        >>> res.terms[["pass_through_percent", "threshold_percent"]].values.tolist()
        [[80.0, 2.0]]
        >>> res.without_clause["con_key"].tolist()
        ['CON-900002']"""
    _need(clause, ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to"], "contracts.clause")
    _need(contract, ["con_key", "type", "price_type"], "contracts.contract", keys=("con_key",))
    c = clause[clause["clause_type"] == "price_adjustment"]
    if as_of is not None:
        c = _clauses_on(c, as_of)
    t = c[["con_key", "clause_no", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to"]].copy()
    t["pass_through_percent"] = np.where(t["param_name"] == "pass_through_percent", t["param_value"], np.nan)
    t["threshold_percent"] = np.where(t["param2_name"] == "threshold_percent", t["param2_value"], np.nan)
    t["n_price_clauses"] = t.groupby("con_key")["clause_no"].transform("size")
    t = t.merge(contract[["con_key", "type", "price_type"]], on="con_key", how="left").sort_values(["con_key", "clause_no"]).reset_index(drop=True)
    cust = contract[contract["type"] == "customer_project"]
    return PriceTerms(t, cust[~cust["con_key"].isin(t["con_key"])][["con_key", "type", "price_type"]].reset_index(drop=True))


def _notification_hours(clause: pd.DataFrame, contract: pd.DataFrame, as_of: Any) -> pd.DataFrame:
    _need(contract, ["con_key", "cus_key"], "contracts.contract", keys=("con_key",))
    _need(clause, ["param_name", "param_value"], "contracts.clause")
    n = _clauses_on(clause, as_of, clause_type="notification")
    hours = n[n["param_name"] == "notification_hours"][["con_key", "param_value", "valid_from"]].rename(columns={"param_value": "notification_hours"})
    if hours["con_key"].duplicated().any():
        raise FrameError(f"contract {hours.loc[hours['con_key'].duplicated(), 'con_key'].iloc[0]} has more than one notification clause on this date")
    out = hours.merge(contract[["con_key", "cus_key"]], on="con_key", how="left")
    return out[["con_key", "cus_key", "notification_hours", "valid_from"]].sort_values(["cus_key", "con_key"], na_position="last").reset_index(drop=True)


@staged(sources=_CLAUSE_SRC + ("contracts.contract.cus_key",), kb=_KB, oracle="py:tests/test_contracts.py::test_incident_notification_clauses")
def notification_clauses_on(clause: pd.DataFrame, contract: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the notification clauses valid on a date, one row per contract with its notification hours.

    One row per contract, not per customer: a customer with several contracts has several rows, and their hours can differ (see notification_hours_by_customer). Contracts without a customer (cus_key null) are kept. The hours are the parameter notification_hours of the clauses of type notification.

    Args:
        clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, param_name, param_value, valid_from and valid_to.
        contract: The contracts.contract frame, one row per con_key; it needs con_key and cus_key.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with con_key, cus_key, notification_hours (the parameter of that name) and valid_from, sorted by cus_key (nulls last) and con_key, index reset.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract frame repeats a con_key; a contract has more than one notification clause on the date; valid_from or valid_to holds a value that is not a date; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import notification_clauses_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> clause = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "clause_no": [1, 1], "clause_type": ["notification", "notification"],
        ...                        "param_name": ["notification_hours", "notification_hours"], "param_value": [24.0, 48.0],
        ...                        "valid_from": ["2025-01-01", "2025-01-01"], "valid_to": [None, None]})
        >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "cus_key": ["CUS-900001", "CUS-900001"]})
        >>> notification_clauses_on(clause, con, "2026-01-01", context=ctx)[["con_key", "notification_hours"]].values.tolist()
        [['CON-900001', 24.0], ['CON-900002', 48.0]]"""
    return _notification_hours(clause, contract, as_of)


@staged(sources=_CLAUSE_SRC + ("contracts.contract.cus_key",), kb=_KB, oracle="py:tests/test_contracts.py::test_incident_notification_clauses")
def notification_hours_by_customer(clause: pd.DataFrame, contract: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the notification hours on a date summed up per customer, with the smallest and largest hours and whether its contracts disagree.

    The plan reads the notification hours per customer; notification_clauses_on is per contract. Columns: cus_key, min_hours, max_hours, n_contracts (contracts of the customer with a notification clause on the date) and mixed (True when the contracts of the customer do not all have the same hours: the customer has no single answer, read min_hours and max_hours). Contracts without a customer are left out.

    Args:
        clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, param_name, param_value, valid_from and valid_to.
        contract: The contracts.contract frame, one row per con_key; it needs con_key and cus_key.
        as_of: The day to check (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with cus_key, min_hours, max_hours, n_contracts and mixed, one row per customer, sorted by cus_key, index reset.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract frame repeats a con_key; a contract has more than one notification clause on the date; valid_from or valid_to holds a value that is not a date; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import notification_hours_by_customer
        >>> ctx = Context(stage="month12", role="analyst")
        >>> clause = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "clause_no": [1, 1], "clause_type": ["notification", "notification"],
        ...                        "param_name": ["notification_hours", "notification_hours"], "param_value": [24.0, 48.0],
        ...                        "valid_from": ["2025-01-01", "2025-01-01"], "valid_to": [None, None]})
        >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "cus_key": ["CUS-900001", "CUS-900001"]})
        >>> out = notification_hours_by_customer(clause, con, "2026-01-01", context=ctx)
        >>> out[["cus_key", "min_hours", "max_hours", "n_contracts", "mixed"]].values.tolist()
        [['CUS-900001', 24.0, 48.0, 2, True]]"""
    n = _notification_hours(clause, contract, as_of)
    n = n[n["cus_key"].notna()]
    g = n.groupby("cus_key")["notification_hours"]
    out = pd.DataFrame({"min_hours": g.min(), "max_hours": g.max(), "n_contracts": g.size().astype("int64")})
    out["mixed"] = out["min_hours"] != out["max_hours"]
    return out.reset_index().sort_values("cus_key").reset_index(drop=True)


@staged(sources=tuple(f"contracts.obligation.{c}" for c in ("con_key", "obligation_no", "due_date", "status", "completed_date", "triggered_on", "deadline_value", "deadline_unit", "met_deadline")),
        kb=_KB, oracle="py:tests/test_contracts.py::test_obligations_are_consistent")
def obligation_status(obligation: pd.DataFrame, as_of: DateLike) -> pd.DataFrame:
    """Use this when you need the status of each contract obligation on a date, worked out from its dates, and whether its deadline was met.

    The status is completed (completed_date on or before the date), overdue (not completed and due_date before the date) or open. For obligations with a trigger and a deadline, `met_recomputed` is whether it was completed on or before triggered_on plus the deadline (hours counted as whole days rounded up: the release compares dates, not hours; null while not completed). For an obligation without a trigger that carries a stored met_deadline, `met_recomputed` is completed_date on or before due_date (null while not completed on the date); an obligation that has a trigger keeps the trigger rule above, also when its unit is not read (null). Obligations without a stored met_deadline have no recomputed result. The stored status and met_deadline stay beside as stored_status and stored_met_deadline. The stored statuses waived, breached, in_force and closed are kept (the dates cannot derive them). Deadline units hours, days and weeks are read; an obligation with another unit has no recomputed result.

    Args:
        obligation: The contracts.obligation frame, one row per con_key and obligation_no; it needs con_key, obligation_no, due_date, status, completed_date, triggered_on, deadline_value, deadline_unit and met_deadline.
        as_of: The day of the status (a date, a Timestamp or an ISO text); a time of day is dropped.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with the columns of the obligation frame except status and met_deadline, plus status_on, met_recomputed (nullable boolean), stored_status, stored_met_deadline and as_of, sorted by con_key and obligation_no, index reset.

    Raises:
        FrameError: obligation is not a DataFrame, has duplicate column names, lacks a needed column or repeats a con_key and obligation_no; due_date, completed_date or triggered_on holds a value that is not a date; as_of is a number, has a time zone or is not a date.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import obligation_status
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ob = pd.DataFrame({"con_key": ["CON-900001", "CON-900001", "CON-900001"], "obligation_no": [1, 2, 3],
        ...                    "due_date": ["2026-01-10", "2026-01-10", "2026-03-01"], "status": ["open", "open", "open"],
        ...                    "completed_date": ["2026-01-05", None, None], "triggered_on": [None, None, None],
        ...                    "deadline_value": [None, None, None], "deadline_unit": [None, None, None], "met_deadline": [None, None, None]})
        >>> obligation_status(ob, "2026-02-01", context=ctx)["status_on"].tolist()
        ['completed', 'overdue', 'open']"""
    _need(obligation, ["con_key", "obligation_no", "due_date", "status", "completed_date", "triggered_on", "deadline_value", "deadline_unit", "met_deadline"], "contracts.obligation", keys=("con_key", "obligation_no"))
    o = _dates(obligation, ["due_date", "completed_date", "triggered_on"], "contracts.obligation")
    d = _day(as_of)
    done = o["completed_date"].notna() & (o["completed_date"] <= d)
    status = np.where(o["status"].isin(_KEPT_STATUS), o["status"], np.where(done, "completed", np.where(o["due_date"] < d, "overdue", "open")))
    value = o["deadline_value"].astype(float)
    days = np.where(o["deadline_unit"] == "hours", np.ceil(value / 24), np.where(o["deadline_unit"] == "days", np.ceil(value), np.where(o["deadline_unit"] == "weeks", np.ceil(value * 7), np.nan)))
    due = o["triggered_on"].to_numpy("datetime64[ns]") + (np.nan_to_num(days, nan=0).astype("int64")).astype("timedelta64[D]")
    has = o["triggered_on"].notna().to_numpy() & ~np.isnan(days)
    met = pd.Series(pd.NA, index=o.index, dtype="boolean")
    ok = has & done.to_numpy()
    met[ok] = (o["completed_date"].to_numpy("datetime64[ns]")[ok] <= due[ok])
    plain = (o["triggered_on"].isna() & o["met_deadline"].notna() & done & o["due_date"].notna()).to_numpy()
    met[plain] = (o["completed_date"].to_numpy("datetime64[ns]")[plain] <= o["due_date"].to_numpy("datetime64[ns]")[plain])
    out = o.assign(status_on=status, met_recomputed=met, stored_status=obligation["status"], stored_met_deadline=obligation["met_deadline"], as_of=d)
    return out.drop(columns=["status", "met_deadline"]).sort_values(["con_key", "obligation_no"]).reset_index(drop=True)


@staged(sources=_CLAUSE_SRC + ("contracts.contract.prj_key", "projects.project.country"), facts=tuple(_WARRANTY.values()), kb=_KB, oracle="py:tests/test_contracts.py::test_warranty_follows_legal_parameters")
def legal_flags(clause: pd.DataFrame, contract: pd.DataFrame, project: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the clauses that carry a verify mark or a legal note, with the works warranty years checked against the legal value of the project's country.

    The verify mark and the legal note always agree in the data. For the works warranty clauses (clause_type warranty, variant works, parameter warranty_years) the warranty years are compared with the legal fact of the project's country (DK or DE: legal.contracts.warranty_years.DK and legal.contracts.warranty_years.DE): warranty_expected and warranty_matches. A works warranty of a contract with no project, or of another country, has no check (null). Columns: con_key, clause_no, clause_type, variant, verify, legal_note, country, warranty_years, warranty_expected, warranty_matches, fact_status (the status of the fact used: VERIFY for the provisional legal values).

    Args:
        clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, variant, param_name, param_value, verify and legal_note.
        contract: The contracts.contract frame, one row per con_key; it needs con_key and prj_key.
        project: The projects.project frame, one row per prj_key; it needs prj_key and country.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A DataFrame with con_key, clause_no, clause_type, variant, verify, legal_note, country, warranty_years, warranty_expected, warranty_matches (nullable boolean) and fact_status, sorted by con_key and clause_no, index reset.

    Raises:
        FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract or project frame repeats its key; clause.verify has nulls.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.delivery import legal_flags
        >>> ctx = Context(stage="month12", role="analyst")
        >>> clause = pd.DataFrame({"con_key": ["CON-900001", "CON-900001"], "clause_no": [1, 2], "clause_type": ["warranty", "payment"],
        ...                        "variant": ["works", "std"], "param_name": ["warranty_years", "days"], "param_value": [5.0, 30.0],
        ...                        "verify": [True, False], "legal_note": ["check", None]})
        >>> con = pd.DataFrame({"con_key": ["CON-900001"], "prj_key": ["PRJ-900001"]})
        >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "country": ["DK"]})
        >>> out = legal_flags(clause, con, prj, context=ctx)
        >>> out[["clause_no", "country"]].values.tolist()
        [[1, 'DK']]
        >>> bool(out["warranty_expected"].notna().iloc[0])
        True"""
    _need(clause, ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "verify", "legal_note"], "contracts.clause")
    _need(contract, ["con_key", "prj_key"], "contracts.contract", keys=("con_key",))
    _need(project, ["prj_key", "country"], "projects.project", keys=("prj_key",))
    if clause["verify"].isna().any():
        raise FrameError("contracts.clause.verify has nulls")
    c = clause[clause["verify"].astype(bool) | clause["legal_note"].notna()].copy()
    c["country"] = c["con_key"].map(contract.set_index("con_key")["prj_key"]).map(project.set_index("prj_key")["country"])
    works = (c["clause_type"] == "warranty") & (c["variant"] == "works") & (c["param_name"] == "warranty_years")
    expected = pd.Series(np.nan, index=c.index)
    status = pd.Series("", index=c.index, dtype=object)
    for cc, fid in _WARRANTY.items():
        f = fact(fid)
        m = works & (c["country"] == cc)
        expected[m] = float(f.value)
        status[m] = combine_status([f.status])
    c["warranty_years"] = np.where(works, c["param_value"], np.nan)
    c["warranty_expected"] = expected
    c["warranty_matches"] = pd.Series(pd.NA, index=c.index, dtype="boolean")
    has = works & expected.notna()
    c.loc[has, "warranty_matches"] = (c.loc[has, "warranty_years"] == expected[has]).astype("boolean")
    c["fact_status"] = status.where(status != "", cast(Any, None))
    cols = ["con_key", "clause_no", "clause_type", "variant", "verify", "legal_note", "country", "warranty_years", "warranty_expected", "warranty_matches", "fact_status"]
    return c[cols].sort_values(["con_key", "clause_no"]).reset_index(drop=True)
