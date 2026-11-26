# check_polymorphic

```python
check_polymorphic(frame: pd.DataFrame, key_column: str, type_column: str, mapping: Mapping[Any, str | None] | None = None) -> pd.DataFrame
```

Use this when a key column can hold keys of different kinds and a type column says which kind each row has, and you need the rows where the two disagree.

Rule: for each distinct pair of type and key (rows with a null key are skipped) the prefix is the text of the key before the first dash. With a mapping the type must be a key of the mapping and the prefix must equal its value; a value None means the type is free text and is not checked. Without a mapping the type value itself is the expected prefix. A type that is not in the mapping gives "unknown_type", a prefix that differs gives "wrong_prefix".

## Args

frame: The frame that holds both columns.
key_column: The column with the keys.
type_column: The column with the type of each key.
mapping: A mapping from a type value to the expected prefix, or None for a type that is not checked. Optional; without it the type column holds the prefix.

## Returns

pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; the table is the name of the key column. Empty when all rows agree.

## Raises

FrameError: key_column or type_column is not a column of the frame.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_polymorphic
>>> frame = pd.DataFrame({"t": ["employee", "external", "employee"], "k": ["EMP-000001", "CNT-000001", "CNT-000002"]})
>>> check_polymorphic(frame, "k", "t", {"employee": "EMP", "external": "CNT"})[["key", "rule", "detail"]]
          key          rule                                  detail
0  CNT-000002  wrong_prefix  t='employee' implies EMP, key has CNT
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
