# parse_label

```python
parse_label(text: str) -> LabelParts
```

Use this when you have a natural label (a budget, forecast, waste or ground label) or a GL account and need its parts.

Rule: the text before the first dash picks the label kind; the label must match the pattern of its kind. A GL account is read as a key of the GL prefix.

## Args

text: The label as text.

## Returns

LabelParts: prefix, text, source, table and column of the master.

## Raises

KeyFormatError: the text is not a known label or does not match the pattern of its kind.

## Example

```python
>>> from halvaro.core import parse_label
>>> label = parse_label("GL-7000")
>>> label.prefix, label.table
('GL', 'gl_account')
>>> parse_label("XX-1")
Traceback (most recent call last):
...
halvaro.core.errors.KeyFormatError: 'XX-1' is not a natural label; known: ...
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
