# holiday_year_bounds

```python
holiday_year_bounds(label: str) -> tuple[dt.date, dt.date]
```

Use this when you have the label of a holiday year and need its first and last day.

The country is read from the label format (DK "2026/27", DE "2026"). The first day is the start month and day of the holiday year of that country (legal facts) in the start year of the
label. The last day is the day before the next holiday year starts.

## Args

label: Holiday year label, for example "2026/27" or "2026".

## Returns

(first_day, last_day) as dates, both inclusive.

## Raises

FrameError: the label matches no label format.

## Example

```python
>>> from halvaro.hr import holiday_year_bounds
>>> first_day, last_day = holiday_year_bounds("2026/27")
>>> first_day.year, last_day.year
(2026, 2027)
>>> (last_day - first_day).days >= 364
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.holiday_year_start.month`, `legal.DE.holiday.holiday_year_start.month`, `legal.DK.holiday.holiday_year_start.day`, `legal.DE.holiday.holiday_year_start.day`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: none (inputs are passed in).
