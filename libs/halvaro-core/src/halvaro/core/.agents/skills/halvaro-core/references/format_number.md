# format_number

```python
format_number(x: Any, decimals: int = 0) -> str
```

Use this when you write a number into a text, a table or a figure label.

Rule: thousands separator comma, decimal point, rounding half away from zero, a minus sign and no scientific notation. None and NaN give n/a.

## Args

x: One number; None and NaN are allowed.
decimals: The number of decimals, a whole number from 0 to 6. Default 0.

## Returns

str: the text, for example 1,235 for 1234.5 with no decimals.

## Raises

FrameError: x is not one number (a list or a text), or decimals is not a whole number from 0 to 6.

## Example

```python
>>> from halvaro.core import format_number
>>> format_number(1234.5, 1), format_number(-1234567.891), format_number(None)
('1,234.5', '-1,234,568', 'n/a')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
