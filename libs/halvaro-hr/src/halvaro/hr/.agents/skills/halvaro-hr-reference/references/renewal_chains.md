# renewal_chains

```python
renewal_chains(cert: pd.DataFrame, *, context: Context | None = None) -> pd.DataFrame
```

Use this when you need to see how certificates follow each other for a person and qualification: the chains of renewals, with lapses and overlaps.

Rule: a certificate with no renews_issued starts a chain; a renewal names the issue date of the one it renews. link_ok says that renews_issued is the previous issue. lapse_days are the days without a valid certificate before this one, overlap_days the days both are valid; both are given only for a renewal whose link is ok.

## Args

cert: Certification frame (competence.certification_held) with emp_key, qual_key, issued, expires, origin, event_no and renews_issued.
context: The caller (stage and role of the session). Optional keyword: when given, a source above its stage is refused before the function runs; without it nothing is checked.

## Returns

pandas.DataFrame: the certificate rows with chain, position, previous issue and expiry, link_ok, covered_until, lapse_days and overlap_days.

## Raises

FrameError: a column is missing or duplicated, a key or issued date is missing, or a certificate expires before it is issued.
StageRefusal: a context is given and its stage does not hold the competence source.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import renewal_chains
>>> cert = pd.DataFrame({"emp_key": ["EMP-000001"] * 2, "qual_key": ["QUAL-01"] * 2, "issued": ["2022-01-01", "2023-12-01"], "expires": ["2023-12-31", "2025-12-31"],
...                      "origin": ["initial", "renewal"], "event_no": [1, 2], "renews_issued": [None, "2022-01-01"]})
>>> renewal_chains(cert)[["position", "link_ok", "lapse_days", "overlap_days"]].fillna(-1).values.tolist()
[[1, True, -1.0, -1.0], [2, True, 0.0, 31.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `competence.certification_held.emp_key`, `competence.certification_held.qual_key`, `competence.certification_held.issued`, `competence.certification_held.expires`, `competence.certification_held.origin`, `competence.certification_held.event_no`, `competence.certification_held.renews_issued`.
