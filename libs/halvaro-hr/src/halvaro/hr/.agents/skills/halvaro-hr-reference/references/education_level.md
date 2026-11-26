# education_level

```python
education_level(education: pd.DataFrame, *, context: Context | None = None) -> pd.Series
```

Use this when you need the highest education level of each person from the education records.

Rule: the highest level_rank per person; people without a record are not in the result. The rank scale is in the competence config.

## Args

education: Education record frame (competence.education_record) with emp_key and level_rank (whole numbers, zero or more, no nulls).
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.Series named education_rank, indexed by emp_key and sorted by it.

## Raises

FrameError: a column is missing, a key is null, or level_rank is not a whole number of zero or more.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import education_level
>>> education = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001", "EMP-000002"], "level_rank": [2, 3, 1]})
>>> education_level(education).to_dict()
{'EMP-000001': 3, 'EMP-000002': 1}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.education_record.emp_key`, `competence.education_record.level_rank`.
