# source_stage

```python
source_stage(source: str) -> str
```

Use this when you need to know at which stage a source (hr, finance, projects and so on) becomes visible to a session.

## Args

source: The name of the source, for example "hr".

## Returns

str: the stage, one of day1, month3 and month12.

## Raises

FrameError: the source is not known; the message lists the known sources.

## Example

```python
>>> from halvaro.core import source_stage
>>> source_stage("hr"), source_stage("finance")
('day1', 'month3')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
