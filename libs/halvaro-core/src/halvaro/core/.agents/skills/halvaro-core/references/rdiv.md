# rdiv

```python
rdiv(a: Any, b: int) -> Any
```

Use this when you divide whole cents by a whole number and the result must be whole cents too.

Rule: integer division rounded half away from zero, so 7 divided by 2 is 4 and minus 7 divided by 2 is minus 4. The divisor should be positive; this is not checked, so a zero divisor gives 0 with a numpy warning.

## Args

a: The dividend, one whole number or an array of them.
b: The divisor, a positive whole number.

## Returns

The quotient as whole numbers, of the shape of a.

## Raises

ValueError: a is a text or cannot be converted to numbers (the error of numpy when it converts the values).

## Example

```python
>>> from halvaro.core import rdiv
>>> int(rdiv(7, 2)), int(rdiv(-7, 2)), int(rdiv(6, 4))
(4, -4, 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
