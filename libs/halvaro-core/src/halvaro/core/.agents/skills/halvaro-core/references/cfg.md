# cfg

```python
cfg(file: str, path: str) -> Fact
```

Use this when you know the config file and the key path of a value but not its fact id.

Rule: the file is mapped to the prefix of its facts and the call is the same as fact(prefix + "." + path).

## Args

file: The config file as the snapshot names it, for example "config/world.yaml".
path: The key path inside the file, for example "fx_eur_dkk_fixed".

## Returns

Fact: the fact at that path (id, value, status and file).

## Raises

FactNotFound: the file is not a fact file (the message lists the known files), or no fact has that path.

## Example

```python
>>> from halvaro.core import cfg
>>> cfg("config/world.yaml", "fx_eur_dkk_fixed").id
'world.fx_eur_dkk_fixed'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
