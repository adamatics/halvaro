# check_key_column

```python
check_key_column(frame: pd.DataFrame, column: str, target: str | None = None, allow_null: bool = False) -> pd.DataFrame
```

Use this when you need to check that every value of a key column is a well formed key, and optionally that its prefix is one the dictionary allows for that column.

Rule: each null is a violation "null" unless allow_null is set (one per null row). Each distinct non null value is checked once: a natural label (BUD, FC, GND, WST) must match the pattern of its kind, any other value must look like PREFIX-digits (else "bad_format"), carry a prefix of the key design (else "unknown_prefix") and match the pattern of that prefix (else "bad_format"). When target names a dictionary column that is a foreign key, a well formed key whose prefix is not one of the allowed prefixes of that column is a "wrong_prefix". A target without a foreign key adds no prefix check.

## Args

frame: The frame that holds the key column.
column: The name of the key column in the frame.
target: The dictionary column as source.table.column whose allowed prefixes apply. Optional; it also names the table in the result.
allow_null: True when null keys are allowed. Optional, default False.

## Returns

pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; empty when all keys pass. The table is the target when given, else the column name; the key of a null is empty text.

## Raises

FrameError: the column is not a column of the frame, or target is given and is not a column of the data dictionary.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_key_column
>>> frame = pd.DataFrame({"k": ["EMP-000001", "EMP-1", "DEP-01", None]})
>>> check_key_column(frame, "k", "competence.crew_plan.emp_key")[["key", "rule"]]
         key          rule
0                     null
1     DEP-01  wrong_prefix
2      EMP-1    bad_format
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
