# stage_placeholder

```python
stage_placeholder(refusal: Exception) -> str
```

Use this when you need the panel text for a chart whose source is above the stage of the session: what is missing, at which stage it appears and what the session sees.

Rule: the one-line stage banner of the refusal followed by "The chart is not drawn."; nothing is estimated or drawn.

## Args

refusal: The StageRefusal that the data call raised; any other exception type is rejected.

## Returns

str: the panel text.

## Raises

FrameError: refusal is not a StageRefusal.

## Example

```python
>>> from halvaro.core import StageRefusal, stage_placeholder
>>> stage_placeholder(StageRefusal(["finance.invoice.amount"], "month3", "day1"))
'Needs finance.invoice.amount (appears at stage month3). This session holds stage day1. The chart is not drawn.'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
