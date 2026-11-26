# from_cents

```python
from_cents(cents: Any) -> Any
```

Use this when you have whole cents and need the amount, with a missing value kept as missing.

Rule: cents divided by 100. A null (None, NaN, pd.NA) stays NaN and is never turned into a number.

## Args

cents: One whole number of cents, a list or array of them, or a Series; the index of a Series is kept.

## Returns

The amounts as floats: a number for one value, an array for an array, a Series for a Series.

## Raises

This function raises no error of its own; a value that is not a number raises the error of numpy.

## Example

```python
>>> from halvaro.core import from_cents
>>> float(from_cents(123456))
1234.56
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
