# holiday_year_label

```python
holiday_year_label(country: str, as_of: dt.date) -> str
```

Use this when you need the label of the holiday year that contains a date, for DK or DE.

The start month of the holiday year and the label format of the country are read from the legal facts at call time, so a changed fact changes the label. A date before the start month
belongs to the holiday year that began in the previous calendar year.

Rule: the label is the start year of the holiday year written in the label_format fact of the country (DK start year, slash, last two digits of the end year; DE the year).

## Args

country: "DK" or "DE".
as_of: Any date.

## Returns

The label as text, for example "2026/27" (DK) or "2026" (DE).

## Raises

FrameError: country is not "DK" or "DE".

## Example

```python
>>> import datetime as dt
>>> from halvaro.hr import holiday_year_bounds, holiday_year_label
>>> first_day, last_day = holiday_year_bounds("2026/27")
>>> holiday_year_label("DK", first_day), holiday_year_label("DK", last_day)
('2026/27', '2026/27')
>>> holiday_year_label("DK", first_day - dt.timedelta(days=1))
'2025/26'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.holiday_year_start.month`, `legal.DE.holiday.holiday_year_start.month`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`.

Source columns: none (inputs are passed in).
