# is_valid_key

```python
is_valid_key(text: Any, prefix: str | None = None) -> bool
```

Use this when you only need to know whether a text is a valid typed key, without handling an error.

Rule: the text must be a key of a prefix of the key list with the digits of its width; with a prefix it must be a key of that prefix.

## Args

text: The text to test; a value that is not a text is not a key.
prefix: The prefix the key must have. Optional.

## Returns

bool: True for a valid key, False for anything else.

## Raises

Nothing is raised: a text that is not a key gives False.

## Example

```python
>>> from halvaro.core import is_valid_key
>>> is_valid_key("EMP-000001"), is_valid_key("EMP-1"), is_valid_key("EMP-000001", "GL")
(True, False, False)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
