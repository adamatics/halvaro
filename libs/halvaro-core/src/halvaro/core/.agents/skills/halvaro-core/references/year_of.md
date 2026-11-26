# year_of

```python
year_of(period: str, start_month: int) -> int
```

Use this when you need the year, counted from a start month, that a period belongs to: a fiscal year or a holiday year that does not begin in January.

Rule: a period from the start month on belongs to the year it is in; an earlier period belongs to the year before. With start month 1 this is the calendar year.

## Args

period: A period as text, for example "2026-03".
start_month: The month in which the year starts, from 1 to 12. The caller gets it from a fact or a setting of its own.

## Returns

int: the year that starts in the start month and contains the period.

## Raises

PeriodError: the start month is not from 1 to 12, or the period is not of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import year_of
>>> year_of("2026-03", 9), year_of("2026-10", 9), year_of("2026-03", 1)
(2025, 2026, 2026)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
