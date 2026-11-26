# framework_for

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import framework_for`.

```python
framework_for(contract: pd.DataFrame, sup_key: str, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the supplier framework contract that is in force for a supplier on a date.

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
    ['CON-900001']

## Source columns

- `contracts.contract.con_key`
- `contracts.contract.type`
- `contracts.contract.sup_key`
- `contracts.contract.status`
- `contracts.contract.start`
- `contracts.contract.end`
