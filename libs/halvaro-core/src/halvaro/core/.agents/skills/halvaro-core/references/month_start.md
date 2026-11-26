# month_start

```python
month_start(period: str) -> dt.date
```

Use this when you need the first calendar day of a period written YYYY-MM.

## Args

period: A period as text, for example "2026-02".

## Returns

datetime.date: the first day of that month.

## Raises

PeriodError: the text is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import month_start
>>> month_start("2026-02")
datetime.date(2026, 2, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
