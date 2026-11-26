# visible_sources

```python
visible_sources(stage: str) -> frozenset[str]
```

Use this when you need the sources that a session at a stage can see.

Rule: the stages are cumulative, so a later stage sees everything an earlier stage sees.

## Args

stage: The stage, one of day1, month3 and month12.

## Returns

frozenset: the names of the visible sources.

## Raises

ProfileError: the stage is not one of day1, month3 and month12.

## Example

```python
>>> from halvaro.core import visible_sources
>>> "hr" in visible_sources("day1"), "finance" in visible_sources("day1"), "finance" in visible_sources("month3")
(True, False, True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
