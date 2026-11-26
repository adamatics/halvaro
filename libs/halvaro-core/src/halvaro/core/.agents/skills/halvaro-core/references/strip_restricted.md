# strip_restricted

```python
strip_restricted(frame: pd.DataFrame, context: Context) -> pd.DataFrame
```

Use this when you have a frame and must remove the restricted columns (pay, birth date) before a session that may not read them sees it.

Rule: when the context has restricted access the frame is returned as it is. Otherwise every column whose header, read after its last dot, equals the bare name of a restricted column of the data dictionary is dropped, so a qualified header such as 'table.column' or the full 'source.table.column' id cannot carry it past the guard. Other columns, their order and the rows are kept.

## Args

frame: The frame to clean.
context: The caller (stage, role and whether restricted columns may be read).

## Returns

pandas.DataFrame: the frame without the restricted columns, or the same frame when the context may read them.

## Raises

This function raises no error of its own.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context, strip_restricted
>>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hr.employee.birth_date": [0], "team": ["A"]})
>>> list(strip_restricted(frame, Context(stage="day1", role="analyst")).columns)
['emp_key', 'team']
>>> list(strip_restricted(frame, Context(stage="day1", role="analyst", restricted_ok=True)).columns)
['emp_key', 'hr.employee.birth_date', 'team']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
