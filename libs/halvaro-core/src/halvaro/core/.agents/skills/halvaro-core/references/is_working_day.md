# is_working_day

```python
is_working_day(day: dt.date, region: str) -> bool
```

Use this when you need to know whether a date is a working day in a region.

Rule: a working day is Monday to Friday that is no public holiday of the region. The holidays come from public_holidays, which carries the status of the facts it reads (VERIFY).

## Args

day: The date.
region: DK, DE-HH or DE-NI.

## Returns

bool: True on a working day, False on a weekend or a public holiday.

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import is_working_day
>>> is_working_day(dt.date(2026, 3, 11), "DK"), is_working_day(dt.date(2026, 3, 14), "DK")
(True, False)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).
