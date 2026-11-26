# cert_status_on

```python
cert_status_on(cert: pd.DataFrame, as_of: dt.date, stored_at: dt.date | None = None, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need the status of every certificate on a date, worked out from the dates and not read from the stored status.

Rule: not_yet_valid before issued, expired after expires, superseded when a strictly later issue of the same person and qualification is issued and still in force, otherwise valid. matches_stored is set only when as_of equals stored_at, the date the stored status was computed for.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires and status.
as_of: The date.
stored_at: The date the stored status was computed for (the release date). Optional.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: one row per certificate with emp_key, qual_key, issued, expires, as_of, status_on, stored_status and matches_stored (null unless stored_at equals as_of).

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import cert_status_on
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2024-01-01"],
...                      "expires": ["2023-12-31", "2026-12-31"], "status": ["expired", "valid"]})
>>> cert_status_on(cert, dt.date(2025, 6, 1))["status_on"].tolist()
['expired', 'valid']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.certification_held.status`.
