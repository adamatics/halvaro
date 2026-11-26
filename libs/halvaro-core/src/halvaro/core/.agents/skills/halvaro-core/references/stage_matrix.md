# stage_matrix

```python
stage_matrix(function_id: str, frames: Mapping[str, pd.DataFrame], call: Callable[[dict[str, pd.DataFrame], Context], Any], *, role: str = 'test', stages: Sequence[str] | None = None, strict: bool = True) -> list[dict[str, Any]]
```

Use this when you need to prove that a function gives a result where all its sources are visible and refuses, naming the missing sources, where they are not.

Rule: for each stage the call is run with only those frames whose source the stage can see. A stage that sees every registered source of the function must give a result; a stage that misses a source must raise StageRefusal naming exactly the missing sources. A result where a refusal was expected, a refusal naming other sources, or a refusal at a stage that misses none is not ok; any other exception from call propagates.

## Args

function_id: The id of a registered function, for example "halvaro.core.org.cost_centre_of_team".
frames: The frames to offer, as {"source.table": frame}.
call: A function that takes the visible frames (a dict of the same form) and a Context, and runs the function under test.
role: The role written into the Context. Default "test".
stages: The stages to run, in order. Default: all stages of the snapshot.
strict: Whether a row that is not ok raises AssertionError. Default True.

## Returns

list: one dict per stage with the keys stage, expected ("result" or "refusal"), outcome ("result" or "refusal") and ok (True or False).

## Raises

HalvaroError: the function id is not registered.
ProfileError: a stage is not a known stage.
AssertionError: strict is true and a stage did not behave as expected.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import cost_centre_of_team, stage_matrix
>>> frames = {"hr.team": pd.DataFrame({"team_key": ["T1"], "cost_centre_key": ["CC-1"]})}
>>> rows = stage_matrix("halvaro.core.org.cost_centre_of_team", frames, lambda visible, ctx: cost_centre_of_team(visible["hr.team"], "T1"), stages=["day1", "month3"])
>>> [(r["stage"], r["outcome"], r["ok"]) for r in rows]
[('day1', 'result', True), ('month3', 'result', True)]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
