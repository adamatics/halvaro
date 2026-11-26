# join_report

```python
join_report(left: pd.DataFrame, right: pd.DataFrame, on: str | Sequence[str] | None = None, *, left_on: str | Sequence[str] | None = None, right_on: str | Sequence[str] | None = None, how: str = 'left', context: Context | None = None, strict: bool | str = False, validate: str | None = None, suffixes: tuple[str, str] = ('', '_right')) -> JoinResult
```

Use this when you join two frames on key columns and need the keys without a partner, classed as orphan, null_key or master_not_visible_at_stage.

Rule: a null key never matches; it is reported as null_key and its row follows the matched rows. A key whose master source is above the stage of `context` is not an orphan (master_not_visible_at_stage). With strict=True orphans raise UnmatchedKeys on the sides the join has to complete (left for how="left", right for how="right", both otherwise); strict="left" or "right" checks one side whatever the join.

## Args

left: The left frame.
right: The right frame.
on: Key column name, or list of names, present in both frames. Use it or left_on and right_on, not both.
left_on: Key column name or names of the left frame.
right_on: Key column name or names of the right frame, as many as left_on.
how: "inner", "left", "right" or "outer". Default "left".
context: The caller, to tell an orphan from a key whose master is not visible at its stage. Optional.
strict: False, True, "left" or "right". Default False.
validate: Passed to pandas merge, for example "one_to_one". Optional.
suffixes: Suffixes for columns that exist on both sides. Default ("", "_right").

## Returns

JoinResult: .frame is the joined DataFrame, .report is an UnmatchedReport with left_only, right_only and counts (rows, keys, keys without partner, null key rows).

## Raises

FrameError: how or strict is not one of the allowed values, the key columns are not named correctly, a key column is missing in a frame or is called "class".
UnmatchedKeys: strict is set and a checked side has orphan keys.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import join_report
>>> left = pd.DataFrame({"k": ["A", "B", None]})
>>> right = pd.DataFrame({"k": ["A", "C"], "v": [1, 2]})
>>> result = join_report(left, right, on="k")
>>> list(result.frame.columns), result.report.counts["left_only_keys"], result.report.counts["right_only_keys"]
(['k', 'v'], 2, 1)
>>> result.report.left_only.to_dict("records")
[{'k': 'B', 'class': 'orphan'}, {'k': None, 'class': 'null_key'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
