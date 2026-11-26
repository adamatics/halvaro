# lead_time_on

Module `halvaro.delivery.supply`. Import: `from halvaro.delivery import lead_time_on`.

```python
lead_time_on(lead_time: pd.DataFrame, as_of: DateLike, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the lead time in weeks per supplier and item on a date, with the change from the previous lead time.

The lead time is the row valid on the date (valid_from on or before, valid_to null or on or after), with the previous row's value and the change.

Args:
    lead_time: The inventory.lead_time frame; it needs sup_key, itm_key, valid_from, valid_to (null for the open row) and lead_time_weeks (numeric without nulls).
    as_of: The day to read the lead times on, a date, a Timestamp or an ISO text YYYY-MM-DD (a day-first text is refused).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns sup_key, itm_key, lead_time_weeks, valid_from, previous_weeks, change_weeks, change_percent (null without a previous row above zero), one row per supplier and item valid on the date, in the order of sup_key, itm_key.

Raises:
    FrameError: lead_time is not a DataFrame, has duplicate column names or lacks a needed column; lead_time_weeks is not numeric or has nulls; a row has no valid_from, or ends before it starts, or holds a date that is not a date or has a time zone; two rows are valid on the date for one supplier and item; as_of is not an ISO date, is a number or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import lead_time_on
    >>> ctx = Context(stage="month12", role="analyst")
    >>> lt = pd.DataFrame({"sup_key": ["SUP-900001", "SUP-900001"], "itm_key": ["ITM-900001", "ITM-900001"],
    ...                    "valid_from": ["2025-01-01", "2025-06-01"], "valid_to": ["2025-05-31", None], "lead_time_weeks": [10.0, 15.0]})
    >>> r = lead_time_on(lt, "2025-07-01", context=ctx)
    >>> r[["lead_time_weeks", "previous_weeks", "change_weeks", "change_percent"]].to_dict("records")
    [{'lead_time_weeks': 15.0, 'previous_weeks': 10.0, 'change_weeks': 5.0, 'change_percent': 50.0}]

## Source columns

- `inventory.lead_time.sup_key`
- `inventory.lead_time.itm_key`
- `inventory.lead_time.valid_from`
- `inventory.lead_time.valid_to`
- `inventory.lead_time.lead_time_weeks`
