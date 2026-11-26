# month_end

```python
month_end(period: str) -> dt.date
```

Use this when you need the last calendar day of a period written YYYY-MM.

## Args

period: A period as text, for example "2026-02".

## Returns

datetime.date: the last day of that month, leap years included.

## Raises

PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12.

## Example

```python
>>> from halvaro.core import month_end
>>> month_end("2026-02")
datetime.date(2026, 2, 28)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
