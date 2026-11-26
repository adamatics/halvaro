# combine_status

```python
combine_status(statuses: Iterable[str]) -> str
```

Use this when a result rests on several facts and needs one status for its envelope.

Rule: VERIFY beats verified, synthetic is kept next to it, and both are reported. A proposed fact counts as VERIFY because the owner has not decided it. Without any fact the status is ok.

## Args

statuses: The statuses of the facts the result used (verified, VERIFY, synthetic or proposed).

## Returns

str: "ok", "synthetic", "VERIFY" or "VERIFY+synthetic".

## Raises

Nothing is raised: a text that is none of the four statuses is ignored.

## Example

```python
>>> from halvaro.core import combine_status
>>> combine_status(["verified", "VERIFY"]), combine_status([]), combine_status(["proposed", "synthetic"])
('VERIFY', 'ok', 'VERIFY+synthetic')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
