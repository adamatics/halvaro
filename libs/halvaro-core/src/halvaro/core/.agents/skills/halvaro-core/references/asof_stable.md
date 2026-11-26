# asof_stable

```python
asof_stable(call: Callable[[Mapping[str, pd.DataFrame], dt.date], Any], baseline: Mapping[str, pd.DataFrame], later: Mapping[str, pd.DataFrame], as_of: dt.date, *, key: str, allowed_keys: Iterable[Any] = ()) -> bool
```

Use this when you need to prove that a result as of a date does not change when a later data release is loaded, except for rows that an effective dated change may alter.

Rule: the call is run on the baseline frames and on the later frames with the same date. Both results (or the value of each, when it is an envelope) must have the same columns. They are then matched on the key column: a key present on one side only, or with a different value in any shared column (two empty values are equal), counts as changed. Changed keys that are not in allowed_keys fail the check. Row order does not matter.

## Args

call: A function that takes a mapping of frames and the date and returns a frame, or an envelope whose value is a frame.
baseline: The frames of the baseline release, as {"source.table": frame}.
later: The frames of the later release, in the same form.
as_of: The date given to the call for both releases.
key: Name of the column that identifies a row in the result.
allowed_keys: Values of the key column whose rows may differ. Default none.

## Returns

bool: True when the check passes (a failure raises instead).

## Raises

AssertionError: the two results have different columns, or rows differ for a key that is not allowed.
KeyError: the key is not a column of a result.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import asof_stable
>>> base = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 2]})}
>>> later = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 3]})}
>>> call = lambda frames, day: frames["t"]
>>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k", allowed_keys=["B"])
True
>>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k")
Traceback (most recent call last):
...
AssertionError: results at 2026-06-30 differ between releases for k ['B']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
