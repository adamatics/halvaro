# staffing_candidates

```python
staffing_candidates(experience: pd.DataFrame, status: Mapping[str, pd.DataFrame], *, valid: Mapping[str, pd.DataFrame] | None = None, qual_keys: Sequence[str] = ()) -> pd.DataFrame
```

Use this when you want the experience ranking with the staffing status of each person on one or more dates.

Rule: for each label of status the status on that date (available, on_leave, left, not_hired) goes in status_<label> and staffable_<label> is true when it is available. Leavers are shown and never staffable. With valid and qual_keys, certs_<label> is true when the person holds every qualification on that date. The order of the experience frame is kept.

## Args

experience: The output of experience_summary.
status: A mapping of label to the status_on output of that date.
valid: A mapping of label to the valid_on output of that date. Optional; needs qual_keys.
qual_keys: The qualifications to check with valid. Default none.

## Returns

pandas.DataFrame: the experience frame with status_<label>, staffable_<label> and, when valid is given, certs_<label>. A person missing from a status frame gets a null status and is not staffable.

## Raises

FrameError: a status frame has more than one row for a person, or valid is given without qual_keys.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import staffing_candidates
>>> experience = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "rank": [1, 2], "hours": [100.0, 50.0]})
>>> status = {"mar": pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "status": ["available", "on_leave"]})}
>>> staffing_candidates(experience, status)[["emp_key", "status_mar", "staffable_mar"]].values.tolist()
[['EMP-000001', 'available', True], ['EMP-000002', 'on_leave', False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employee.leave_date`, `hr.leave_record.leave_type`.
