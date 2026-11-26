# loader_contract

```python
loader_contract(loader: Any, expected_columns: Mapping[str, list[str]], *, context: Context | None = None, restricted_columns: Iterable[str] = (), where: Mapping[str, tuple[str, Any]] | None = None) -> list[str]
```

Use this when you need to check that an app loader (SQL or API) keeps the loading contract, and get the problems as text.

Rule: for each table the loader is called and checked: the column names are exactly the expected ones, in order; no timestamp column is time zone aware; the columns argument returns just the first two expected columns (only those two are requested); a where condition (column equal to value) is honoured; no restricted column is present when the context does not allow restricted access; and the chunks of iter_chunks put together equal load. One problem is written per broken check. Only the first load call of a table is guarded: a table that fails it is a problem and the other checks of that table are skipped; exceptions raised by later load calls or by iter_chunks propagate. Dtype checks are not run.

## Args

loader: An object with load(source, table, columns=None, where=None) and iter_chunks(source, table, columns=None, where=None), both returning frames.
expected_columns: The exact source column names per table, as {"source.table": [columns]}.
context: The caller. The restricted check runs only when it is given and does not allow restricted access. Default None.
restricted_columns: Names of the restricted columns. Default none.
where: Optional equality conditions as {"source.table": (column, value)}.

## Returns

list: the problems as text, one per broken check, each starting with the table name; empty when the loader passes.

## Raises

ValueError: a table name in expected_columns does not have the form source.table.
KeyError: a where column is not a column of the loaded table.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import loader_contract
>>> class Loader:
...     frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
...     def load(self, source, table, columns=None, where=None):
...         return self.frame if columns is None else self.frame[columns]
...     def iter_chunks(self, source, table, columns=None, where=None):
...         yield self.frame.iloc[:1]
...         yield self.frame.iloc[1:]
>>> loader_contract(Loader(), {"s.t": ["a", "b"]})
[]
>>> loader_contract(Loader(), {"s.t": ["b", "a"]})
["s.t: columns ['a', 'b'] differ from ['b', 'a']"]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
