# require_sources

```python
require_sources(context: Context, sources: Sequence[str], function: str | None = None) -> None
```

Use this when a function reads tables of some sources and must refuse a session whose stage does not hold them yet.

Rule: the sources are reduced to their source name (the part before the first dot). Every source whose stage is above the stage of the context is named in the refusal together with the stage where it appears.

## Args

context: The caller (stage, role, release date, restricted access).
sources: Source names or table names such as "hr.employee" or "finance".
function: The name of the calling function, written into the refusal. Optional.

## Returns

None: nothing happens when every source is visible at the stage of the context.

## Raises

StageRefusal: one or more sources appear at a later stage than the context holds.
FrameError: a source name is unknown, for example "zz"; the message lists the known sources.

## Example

```python
>>> from halvaro.core import Context, require_sources
>>> day1 = Context(stage="day1", role="analyst")
>>> require_sources(day1, ["hr.employee"])
>>> require_sources(day1, ["finance.journal_line"], function="trial_balance")
Traceback (most recent call last):
...
halvaro.core.errors.StageRefusal: Sources finance appear at stage month3; the session holds stage day1 (trial_balance). Ask for a session at stage month3 or use only the sources of stage day1.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
