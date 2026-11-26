# release_now

```python
release_now(data_releases: Mapping[str, pd.DataFrame]) -> ReleaseInfo
```

Use this when you need the one release identity (release, now, generated_at, base seed and increment) that all loaded sources share.

Rule: each data_release frame must hold exactly one row. The five values are compared as text across the sources and must be equal; the result is then built from them, with now as a date, generated_at as a timestamp and increment as a whole number.

## Args

data_releases: The data_release frame of each source as {source: frame}, with the columns release, now, generated_at, base_seed and increment.

## Returns

ReleaseInfo: a named tuple with release (text), now (date), generated_at (timestamp), base_seed (as stored) and increment (whole number).

## Raises

FrameMissing: no frame was passed.
FrameError: a frame does not have exactly one row, increment is not a whole number, or now or generated_at is not a date.
ReleaseMismatch: the sources disagree on one of the five values.
KeyError: a frame lacks one of the five columns.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import release_now
>>> row = {"release": ["r1"], "now": ["2026-11-30"], "generated_at": ["2026-12-01 08:00:00"], "base_seed": ["seed-a"], "increment": [2]}
>>> info = release_now({"hr": pd.DataFrame(row), "finance": pd.DataFrame(row)})
>>> info.release, info.now.isoformat(), info.increment
('r1', '2026-11-30', 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.data_release.release`.
