# clauses_on

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import clauses_on`.

```python
clauses_on(clause: pd.DataFrame, as_of: DateLike, *, con_key: str | None = None, clause_type: str | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the contract clauses that are valid on a date, optionally for one contract and one clause type.

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
    [2]

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
