# table_key

```python
table_key(source_table: str) -> tuple[str, ...]
```

Use this when you need the columns that make up the primary key of a table, composite keys included.

Rule: the key columns are read from the table keys of the release, in the order they are listed there.

## Args

source_table: The table as source.table, for example "competence.crew_plan".

## Returns

tuple: the names of the key columns, one for a simple key and several for a composite key.

## Raises

FrameError: the table is not a table of the release.

## Example

```python
>>> from halvaro.core import table_key
>>> table_key("competence.crew_plan")
('prj_key', 'emp_key')
>>> table_key("competence.nothing")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: competence.nothing is not a table of the release; use source.table
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
