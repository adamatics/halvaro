# period_of

```python
period_of(day: dt.date) -> str
```

Use this when you have a date and need its period written YYYY-MM.

## Args

day: A date (a datetime.date or a timestamp).

## Returns

str: the period, for example 2026-03.

## Raises

PeriodError: day is not a date or a timestamp (a text, for example).

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import period_of
>>> period_of(dt.date(2026, 3, 31))
'2026-03'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
