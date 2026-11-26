# add_working_days

```python
add_working_days(start: dt.date, n: int, region: str) -> dt.date
```

Use this when you need the date that is a number of working days from a start date, the start date counting as the first when it is a working day.

Rule: the n-th working day on or after start. Weekends and the public holidays of the region are skipped.

## Args

start: The first day to look at.
n: Which working day, 1 or more. With 1 the result is the start itself when it is a working day.
region: DK, DE-HH or DE-NI.

## Returns

datetime.date: the n-th working day on or after start.

## Raises

FrameError: n is less than 1.
UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import add_working_days
>>> friday = dt.date(2026, 3, 13)
>>> add_working_days(friday, 1, "DK"), add_working_days(friday, 2, "DK")
(datetime.date(2026, 3, 13), datetime.date(2026, 3, 16))
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).
