# term_changes

```python
term_changes(term: pd.DataFrame) -> pd.DataFrame
```

Use this when you need the events behind the employment terms: one row per name in the change reason of each term.

Rule: a change reason such as pay_review+promotion gives two events with combined true; a single name gives one event with combined false. The known names are hire, window_start, summary, pay_review, promotion and fte_change.

## Args

term: Employment term frame (hr.employment_term) with emp_key, valid_from and change_reason.

## Returns

pandas.DataFrame with emp_key, valid_from, event and combined, sorted by person, date and event.

## Raises

FrameError: a column is missing, a term has no change_reason, or a name is not one of the known names.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import term_changes
>>> term = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "valid_from": ["2024-01-01", "2025-01-01"], "change_reason": ["hire", "pay_review+promotion"]})
>>> term_changes(term)[["valid_from", "event", "combined"]].to_dict("records")
[{'valid_from': '2024-01-01', 'event': 'hire', 'combined': False}, {'valid_from': '2025-01-01', 'event': 'pay_review', 'combined': True}, {'valid_from': '2025-01-01', 'event': 'promotion', 'combined': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.employment_term.emp_key`, `hr.employment_term.change_reason`, `hr.employment_term.valid_from`.
