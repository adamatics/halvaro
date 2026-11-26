# column_prefixes

```python
column_prefixes(column: str) -> tuple[str, ...]
```

Use this when you need the key prefixes that a column of the data dictionary may hold, taken from its foreign key target.

Rule: the prefixes are read from the dictionary for the column; a polymorphic column has several, and a column that is no foreign key has none.

## Args

column: The dictionary column as source.table.column, for example "competence.crew_plan.emp_key".

## Returns

tuple: the allowed prefixes as text, for example ('EMP',); empty when the column is no foreign key.

## Raises

FrameError: the column is not a column of the data dictionary.

## Example

```python
>>> from halvaro.core import column_prefixes
>>> column_prefixes("competence.crew_plan.emp_key")
('EMP',)
>>> column_prefixes("competence.crew_plan.nothing")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: competence.crew_plan.nothing is not a column of the data dictionary; use source.table.column
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
