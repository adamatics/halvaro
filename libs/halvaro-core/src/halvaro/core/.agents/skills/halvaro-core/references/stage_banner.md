# stage_banner

```python
stage_banner(refusal: HalvaroError) -> str
```

Use this when a stage or column refusal must be shown to the user as one plain line.

Rule: a StageRefusal gives the missing sources, the stage where they appear and the stage the session holds. A RestrictedColumnRefusal gives the column, the role and the stage. Any other error gives its own message text.

## Args

refusal: The error that was raised, normally a StageRefusal or a RestrictedColumnRefusal.

## Returns

str: one line of text.

## Raises

This function raises no error of its own.

## Example

```python
>>> from halvaro.core import StageRefusal, stage_banner
>>> stage_banner(StageRefusal(["finance"], "month3", "day1"))
'Needs finance (appears at stage month3). This session holds stage day1.'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
