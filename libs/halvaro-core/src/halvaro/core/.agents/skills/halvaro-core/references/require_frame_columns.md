# require_frame_columns

```python
require_frame_columns(frame: pd.DataFrame, source_table: str, columns: Sequence[str] | str) -> None
```

Use this when a loaded frame must carry the source column names of a table before you use it, so a renamed or dropped column is caught early.

Rule: the table must be a 'source.table' of the data dictionary, every named column must be a column of that table in the dictionary, and every named column must exist in the frame. Extra columns in the frame are fine.

## Args

frame: The loaded frame of the table.
source_table: The table as source.table, for example "hr.employee".
columns: The column names the caller needs, as a list or a single name.

## Returns

None: nothing happens when all named columns are in the dictionary and in the frame.

## Raises

FrameError: source_table is not a source.table of the data dictionary, a named column is not a column of that table in the dictionary, or a named column is missing in the frame.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import require_frame_columns
>>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"]})
>>> require_frame_columns(frame, "hr.employee", ["emp_key", "hire_date"])
>>> require_frame_columns(frame, "hr.employee", ["emp_key", "email"])
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: the frame for hr.employee lacks column(s) email; it has emp_key, hire_date. Load the source column names without renaming them.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
