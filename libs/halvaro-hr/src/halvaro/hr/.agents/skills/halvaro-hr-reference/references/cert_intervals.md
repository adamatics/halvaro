# cert_intervals

```python
cert_intervals(cert: pd.DataFrame, *, context: Context | None = None) -> dict[tuple[str, str], list[tuple[Any, Any]]]
```

Use this when you check coverage for many projects and want to build the validity intervals of the certificates once.

Rule: every certificate is an interval from issued to expires (an empty expires is open); the intervals of one person and qualification are listed together. Pass the result to coverage_gap(..., intervals=...) to avoid building it again.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued and expires.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

dict: {(emp_key, qual_key): [(issued, expires), ...]} with NaT for an open end.

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import cert_intervals
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"], "qual_key": ["QUAL-01"], "issued": ["2024-01-01"], "expires": [None]})
>>> intervals = cert_intervals(cert)
>>> list(intervals), len(intervals[("EMP-000001", "QUAL-01")])
([('EMP-000001', 'QUAL-01')], 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`.
