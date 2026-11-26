# add_months

```python
add_months(period: str, n: int) -> str
```

Use this when you need the period a number of months after, or before, a period.

## Args

period: A period as text, for example "2026-11".
n: Number of months to move. Negative moves back; zero returns the same period.

## Returns

str: the period YYYY-MM, with the year carried over.

## Raises

PeriodError: the text is not a period of the form YYYY-MM, or the result is outside the years 0001 to 9999.

## Example

```python
>>> from halvaro.core import add_months
>>> add_months("2026-11", 3), add_months("2026-01", -1)
('2027-02', '2025-12')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
