# working_days

```python
working_days(start: dt.date, end: dt.date, region: str) -> int
```

Use this when you need the number of working days between two dates in a region, both days included.

Rule: each day of the range is counted when is_working_day is true for the region. A range whose end is before its start has no days and the result is zero.

## Args

start: First day of the range.
end: Last day of the range.
region: DK, DE-HH or DE-NI.

## Returns

int: the number of working days in [start, end].

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI, also for an empty range.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import working_days
>>> working_days(dt.date(2026, 3, 9), dt.date(2026, 3, 13), "DK")
5
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).
