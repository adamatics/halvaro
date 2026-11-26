# period_range

```python
period_range(first: str, last: str) -> list[str]
```

Use this when you need every month between two periods, both included, as a list of periods.

Rule: the list runs from first to last in steps of one month. When last is before first the list is empty.

## Args

first: The first period as text, for example "2026-11".
last: The last period as text.

## Returns

list: the periods YYYY-MM from first to last, oldest first; empty when last is before first.

## Raises

PeriodError: first or last is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import period_range
>>> period_range("2026-11", "2027-02")
['2026-11', '2026-12', '2027-01', '2027-02']
>>> period_range("2027-02", "2026-11")
[]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
