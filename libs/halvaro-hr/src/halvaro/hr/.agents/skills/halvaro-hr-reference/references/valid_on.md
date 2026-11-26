# valid_on

```python
valid_on(cert: pd.DataFrame, as_of: dt.date, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the certificates that are valid on a date, one row per person and qualification.

Rule: a certificate is valid when issued is on or before the date and expires is empty (no expiry) or on or after the date, both ends included. The status column is never read. Per person and qualification the latest issue is kept.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
as_of: The date.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: emp_key, qual_key, issued, expires and as_of, sorted by person and qualification.

## Raises

FrameError: a column is missing or duplicated, a row has no emp_key, qual_key or issued, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import valid_on
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000001"], "qual_key": ["QUAL-01", "QUAL-01"],
...                      "issued": ["2023-01-10", "2025-01-10"], "expires": ["2025-01-09", "2027-01-09"]})
>>> valid = valid_on(cert, dt.date(2026, 11, 30))
>>> valid["qual_key"].tolist(), valid["expires"].dt.strftime("%Y-%m-%d").tolist()
(['QUAL-01'], ['2027-01-09'])
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`.
