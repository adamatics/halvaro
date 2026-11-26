# parse_key

```python
parse_key(text: str) -> KeyParts
```

Use this when you have the text of a typed key such as EMP-000001 and need its prefix, number, width and family.

Rule: the text must be a prefix of the key list, a dash and digits of the width the prefix has. Natural labels such as GL accounts are read by parse_label, not here.

## Args

text: The key as text.

## Returns

KeyParts: prefix, number (a whole number), width (the number of digits), family and entity.

## Raises

KeyFormatError: the text is not a typed key, the prefix is not known, or the digits do not match the width of the prefix.

## Example

```python
>>> from halvaro.core import parse_key
>>> parse_key("EMP-000001")
KeyParts(prefix='EMP', number=1, width=6, family='transactional', entity='employee')
>>> parse_key("EMP-1")
Traceback (most recent call last):
...
halvaro.core.errors.KeyFormatError: 'EMP-1' does not match ^EMP-[0-9]{6}$ (width 6, family transactional)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
