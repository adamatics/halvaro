# format_money

```python
format_money(amount: Any, currency: str, scale: str | None = None, decimals: int | None = None) -> str
```

Use this when you write one amount of one currency into a text, a table or a figure label.

Rule: the currency code, a space and the amount rounded half away from zero; with scale k, m or bn the amount is divided by a thousand, a million or a billion and the letter is appended. Decimals default to 0, or 1 when scaled. A sum over two currencies is refused upstream (see guarded_sum).

## Args

amount: One number; None and NaN give n/a.
currency: DKK, EUR or SEK.
scale: None, "k", "m" or "bn".
decimals: The number of decimals, a whole number from 0 to 6. Default 0, or 1 with a scale.

## Returns

str: the text, for example DKK 1,235.

## Raises

FrameError: the currency is not DKK, EUR or SEK, the scale is not allowed, or amount is not one number.

## Example

```python
>>> from halvaro.core import format_money
>>> format_money(1234.5, "DKK"), format_money(1234567.0, "EUR", "m")
('DKK 1,235', 'EUR 1.2m')
>>> format_money(1.0, "XXX")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: currency 'XXX' is not one of DKK, EUR, SEK
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
