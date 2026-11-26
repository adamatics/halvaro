# statutory_line_of

```python
statutory_line_of(gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the statutory statement line that each ledger account belongs to, for Denmark and for Germany.

Rule: the map code of the account (dk_statutory_map, de_statutory_map) is looked up in the statutory map lines; the line of an account must belong to the country of its map.

## Args

gl_account: Frame finance.gl_account with gl_key, dk_statutory_map and de_statutory_map, one row per account.
statutory_map_line: Frame finance.statutory_map_line with map_code, country, statement, line_order, line_code, label and normal_side, one row per map code.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with gl_key, country, map_code, statement, line_order, line_code, label and normal_side: one row per account and country.

## Raises

FrameError: a column is missing, a key is duplicated, an account has no map, a map code is not in the map lines, or a map belongs to the other country.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import statutory_line_of
>>> ctx = Context(stage="month12", role="analyst")
>>> accounts = pd.DataFrame({"gl_key": ["GL-1"], "dk_statutory_map": ["DK-A"], "de_statutory_map": ["DE-A"]})
>>> lines = pd.DataFrame({"map_code": ["DK-A", "DE-A"], "country": ["DK", "DE"], "statement": ["IS", "IS"], "line_order": [1, 1], "line_code": ["REV", "REV"],
...                       "label": ["Revenue", "Umsatz"], "normal_side": ["credit", "credit"]})
>>> statutory_line_of(accounts, lines, context=ctx)[["gl_key", "country", "line_code", "label"]].sort_values("country").values.tolist()
[['GL-1', 'DE', 'REV', 'Umsatz'], ['GL-1', 'DK', 'REV', 'Revenue']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.gl_account.gl_key`, `finance.gl_account.dk_statutory_map`, `finance.gl_account.de_statutory_map`, `finance.statutory_map_line.map_code`, `finance.statutory_map_line.line_code`.
