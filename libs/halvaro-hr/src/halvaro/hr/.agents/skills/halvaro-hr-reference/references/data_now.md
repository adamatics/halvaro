# data_now

```python
data_now(data_releases: Mapping[str, pd.DataFrame], as_of: dt.date | None = None) -> dt.date
```

Use this when you need the date of the data release (the "now" of the data) and want to refuse a date after it.

Rule: all data_release frames passed must agree; the release date is their now. Ledgers and status caches end there, so a later as_of is refused.

## Args

data_releases: A mapping of source name to its data_release frame (one row each), for example {"hr": frame}.
as_of: Optional date to check against the release date.

## Returns

datetime.date: the release date.

## Raises

FrameMissing: no data_release frame was passed.
FrameError: a data_release frame does not have exactly one row.
ReleaseMismatch: the frames name different releases.
PeriodError: as_of is after the release date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.hr import data_now
>>> release = pd.DataFrame({"release": ["r1"], "now": ["2026-03-31"], "generated_at": ["2026-04-01"], "base_seed": [1], "increment": [0]})
>>> data_now({"hr": release})
datetime.date(2026, 3, 31)
>>> data_now({"hr": release}, dt.date(2026, 4, 30))
Traceback (most recent call last):
...
halvaro.core.errors.PeriodError: as_of 2026-04-30 is after the data release date 2026-03-31: holiday ledgers and status caches end there. Use a date up to 2026-03-31.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.data_release.release`, `hr.data_release.now`.
