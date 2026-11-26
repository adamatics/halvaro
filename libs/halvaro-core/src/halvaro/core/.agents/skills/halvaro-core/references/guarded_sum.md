# guarded_sum

```python
guarded_sum(frame: pd.DataFrame, value: str, *, by: str | Iterable[str] = (), guard: str | Iterable[str] | None = None) -> pd.DataFrame
```

Use this when you need the sum of an amount or quantity column and must be sure that no two currencies or units are added together.

Rule: the value column is summed per group of the by columns as the plain sum of the stored numbers, with no rounding and no conversion to cents. Each guard column (default: currency, unit or both, whichever the frame has) may hold at most one distinct non null value inside each group; a group that mixes values is refused. Group on the guard column to get one sum per currency. Null values are skipped and an all null group sums to 0. Groups with a null key are kept.

## Args

frame: The rows to sum.
value: The column to sum.
by: The column or columns to group by, a name or a list. Optional; without it the result is one row with the sum of all rows.
guard: The column or columns that must not mix inside a group. Optional; default currency and unit when the frame has them.

## Returns

pandas.DataFrame: the by columns followed by the value column, one row per group sorted by the by columns; one row with only the value column when by is empty.

## Raises

FrameError: the value column, a by column or a guard column is missing, or the frame has no guard column at all and none was named.
SumGuardError: a group has more than one distinct value in a guard column.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import guarded_sum
>>> frame = pd.DataFrame({"currency": ["DKK", "DKK", "EUR"], "amount": [1.5, 2.25, 4.0]})
>>> guarded_sum(frame, "amount", by="currency")
  currency  amount
0      DKK    3.75
1      EUR    4.00
>>> guarded_sum(frame, "amount")
Traceback (most recent call last):
...
halvaro.core.errors.SumGuardError: the rows to sum carry more than one currency (DKK, EUR); group by currency or convert first (core.convert).
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
