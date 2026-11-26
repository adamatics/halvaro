# line_with_gaps

```python
line_with_gaps(x: Iterable[Any] | pd.Series, y: Iterable[Any] | pd.Series, *, interval: float | dt.timedelta | None = None, factor: float = 1.5) -> pd.DataFrame
```

Use this when you need the points of a line with a null row inserted where the step to the next x is too large, so that a plot breaks there instead of joining across the gap.

Rule: the points are sorted by x (stable). Where the step to the next x is strictly more than the threshold, a row is inserted with x halfway through the gap and y null; a gap is never filled
with zero and a null y stays null. The threshold is `factor` times `interval` when the caller passes the sampling interval, else `factor` times the median step (1.5 is proposed). Rows with a NaN x sort last and are kept. With fewer than two points the sorted points are returned as they are.

## Args

x: The x values (numbers or dates), as a list, array or Series.
y: The y values, one per x.
interval: The sampling interval, a number or a timedelta for dates; None takes the median step.
factor: How many intervals a step may take before the line breaks (proposed 1.5).

## Returns

pandas.DataFrame with the columns x and y, sorted by x, with a row of null y added in every gap.

## Raises

FrameError: x or y is a scalar or a text and not a list, array or Series, x holds text or other values that are neither numbers nor dates, the interval is not a timedelta for dates or not a number for numbers, x and y differ in length, or the interval (given or median) is zero, negative or unknown; a median step of zero raises it even when a real gap exists (pass interval=).

## Example

```python
>>> from halvaro.core import line_with_gaps
>>> line_with_gaps([1, 2, 3, 6, 7], [10, 20, 30, 60, 70]).to_dict("list")
{'x': [1.0, 2.0, 3.0, 4.5, 6.0, 7.0], 'y': [10.0, 20.0, 30.0, nan, 60.0, 70.0]}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
