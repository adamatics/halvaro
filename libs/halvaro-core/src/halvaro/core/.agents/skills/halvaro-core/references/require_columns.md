# require_columns

```python
require_columns(context: Context, columns: Sequence[str]) -> None
```

Use this when a function reads columns that are restricted (pay, birth date) and must refuse a session that may not read them.

Rule: only the columns that the data dictionary lists as restricted count. When the context has restricted access nothing happens.

## Args

context: The caller (stage, role and whether restricted columns may be read).
columns: Column ids of the form source.table.column, for example "hr.employment_term.base_salary".

## Returns

None: nothing happens when no column is restricted or the context may read them.

## Raises

RestrictedColumnRefusal: a column is restricted and the context has no restricted access; the message names the column, the role and the stage.

## Example

```python
>>> from halvaro.core import Context, require_columns
>>> analyst = Context(stage="day1", role="analyst")
>>> require_columns(analyst, ["hr.employee.emp_key"])
>>> require_columns(analyst, ["hr.employment_term.base_salary"])
Traceback (most recent call last):
...
halvaro.core.errors.RestrictedColumnRefusal: Column hr.employment_term.base_salary is restricted; role analyst at stage day1 may not read it. Use an aggregate above the minimum group size or a role with restricted access.
>>> require_columns(Context(stage="day1", role="analyst", restricted_ok=True), ["hr.employment_term.base_salary"])
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
