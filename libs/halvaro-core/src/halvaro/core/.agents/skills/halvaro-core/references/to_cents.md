# to_cents

```python
to_cents(amount: Any) -> Any
```

Use this when you need an amount as whole cents, so that sums and comparisons are exact.

Rule: the amount times 100 rounded to a whole number; a tie goes to the even cent (0.125 is 12.5 cents and gives 12). A null, an infinite amount or an amount whose cents do not fit in 64 bits is refused.

## Args

amount: One amount, a list or array of amounts, or a Series; the index of a Series is kept.

## Returns

The integer cents: a whole number for one amount, an array for an array, a Series for a Series.

## Raises

FrameError: an amount is null, infinite, or has cents that do not fit in 64 bits; the message says how many.

## Example

```python
>>> from halvaro.core import to_cents
>>> int(to_cents(1234.56)), int(to_cents(0.125)), int(to_cents(-0.125))
(123456, 12, -12)
>>> to_cents(float("nan"))
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: to_cents got 1 null amount(s); cents are whole numbers and a null has no cents. Drop or fill the nulls first
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
