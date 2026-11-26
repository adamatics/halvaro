# synthetic_label

```python
synthetic_label() -> str
```

Use this when you need the text 'synthetic data' that goes in the corner of every chart, table and map, in both modes.

Rule: returns the constant text SYNTHETIC_LABEL; nothing is computed.

## Args

None: the function takes no input.

## Returns

str: the text "synthetic data".

## Raises

None: the function takes no input and has no error path.

## Example

```python
>>> from halvaro.core import synthetic_label
>>> synthetic_label()
'synthetic data'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
