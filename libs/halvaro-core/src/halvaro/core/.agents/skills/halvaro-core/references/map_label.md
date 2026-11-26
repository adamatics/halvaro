# map_label

```python
map_label() -> str
```

Use this when you need the label of a map: 'synthetic data' and the basemap attribution, because the networks drawn on the map are fictional (visualisations.md).

Rule: the text SYNTHETIC_LABEL, a semicolon and a space, then the attribution text with a copyright sign and 'OpenStreetMap contributors'; nothing is computed.

## Args

None: the function takes no input.

## Returns

str: the label, "synthetic data; " followed by the attribution.

## Raises

None: the function takes no input and has no error path.

## Example

```python
>>> from halvaro.core import map_label
>>> map_label().startswith("synthetic data; ")
True
>>> map_label().endswith("OpenStreetMap contributors")
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
