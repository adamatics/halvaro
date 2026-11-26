# compare_periods

```python
compare_periods(a: str, b: str) -> int
```

Use this when you need to order two periods written YYYY-MM.

## Args

a: The first period.
b: The second period.

## Returns

int: -1 when a is before b, 0 when they are equal, 1 when a is after b.

## Raises

PeriodError: a or b is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import compare_periods
>>> compare_periods("2026-02", "2026-11"), compare_periods("2026-11", "2026-11"), compare_periods("2027-01", "2026-11")
(-1, 0, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
