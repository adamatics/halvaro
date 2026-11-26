# caption

```python
caption(basis: str | None, as_of: dt.date | pd.Timestamp | str | None) -> str
```

Use this when a figure or a table needs the basis and as-of line under it.

Rule: the line is "<basis>, as of <date>". A missing basis is written "basis not stated" and a missing date "as-of not stated"; neither is left out.

## Args

basis: What the figures are (for example "actual cost"), or None.
as_of: The as-of date as a date, a timestamp or an ISO date text, or None.

## Returns

str: the caption line.

## Raises

FrameError: as_of is neither empty, a date, a timestamp nor an ISO date text.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import caption
>>> caption("actual cost", dt.date(2026, 11, 30)), caption(None, None)
('actual cost, as of 2026-11-30', 'basis not stated, as-of not stated')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
