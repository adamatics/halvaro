# parse_period

```python
parse_period(text: str) -> tuple[int, int]
```

Use this when you have a period written YYYY-MM and need its year and month as numbers.

## Args

text: The period as text, for example "2026-11".

## Returns

tuple: (year, month) as two whole numbers.

## Raises

PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12 and a year from 0001 to 9999.

## Example

```python
>>> from halvaro.core import parse_period
>>> parse_period("2026-11")
(2026, 11)
>>> parse_period("2026-13")
Traceback (most recent call last):
...
halvaro.core.errors.PeriodError: '2026-13' is not a period; expected YYYY-MM such as 2026-11, with a year from 0001 to 9999
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
