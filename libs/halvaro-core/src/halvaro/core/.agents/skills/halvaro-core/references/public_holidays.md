# public_holidays

```python
public_holidays(year: int, region: str) -> frozenset[dt.date]
```

Use this when you need the public holidays of a year in one of the three regions.

Rule: the dates are computed from the Easter date and the fixed dates of the region. The parameters are provisional (VERIFY) and the functions that read them carry that status.

## Args

year: The calendar year.
region: DK, DE-HH or DE-NI.

## Returns

frozenset: the holidays as datetime.date values, all in the year.

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> from halvaro.core import public_holidays
>>> days = public_holidays(2026, "DK")
>>> all(d.year == 2026 for d in days), type(days).__name__
(True, 'frozenset')
>>> public_holidays(2026, "XX")
Traceback (most recent call last):
...
halvaro.core.errors.UnknownRegion: region 'XX' is unknown; use one of DK, DE-HH, DE-NI
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).
