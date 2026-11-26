# format_percent

```python
format_percent(x: Any, decimals: int = 1, *, ratio: bool = False) -> str
```

Use this when you write a percentage into a text, a table or a figure label.

Rule: the number with the sign %. x is already in percent (12.345 gives 12.3%); with ratio=True x is a share (0.12345 gives 12.3%). Rounding half away from zero. None and NaN give n/a.

## Args

x: One number; None and NaN are allowed.
decimals: The number of decimals, a whole number from 0 to 6. Default 1.
ratio: True when x is a share of one and not a percent. Default False.

## Returns

str: the text with the percent sign.

## Raises

FrameError: x is not one number, or decimals is not a whole number from 0 to 6.

## Example

```python
>>> from halvaro.core import format_percent
>>> format_percent(12.345), format_percent(0.256, ratio=True), format_percent(None)
('12.3%', '25.6%', 'n/a')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
