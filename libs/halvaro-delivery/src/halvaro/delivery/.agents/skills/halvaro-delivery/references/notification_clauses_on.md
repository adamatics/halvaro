# notification_clauses_on

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import notification_clauses_on`.

```python
notification_clauses_on(clause: pd.DataFrame, contract: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the notification clauses valid on a date, one row per contract with its notification hours.

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
    [['CON-900001', 24.0], ['CON-900002', 48.0]]

## Source columns

- `contracts.clause.con_key`
- `contracts.clause.clause_no`
- `contracts.clause.clause_type`
- `contracts.clause.variant`
- `contracts.clause.param_name`
- `contracts.clause.param_value`
- `contracts.clause.param2_name`
- `contracts.clause.param2_value`
- `contracts.clause.valid_from`
- `contracts.clause.valid_to`
- `contracts.clause.verify`
- `contracts.clause.legal_note`
- `contracts.contract.cus_key`
