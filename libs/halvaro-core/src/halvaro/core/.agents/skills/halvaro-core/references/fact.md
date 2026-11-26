# fact

```python
fact(fact_id: str) -> Fact
```

Use this when you need the value, the status and the source file of a fact by its id, for example a rate or a legal parameter that a function reads.

Rule: the fact comes from the snapshot of the config files and the authored decisions. Its status (verified, VERIFY, synthetic or proposed) travels with the value, and the caller reports it. A fact that holds a date is returned as a datetime.date.

## Args

fact_id: The id of the fact, for example "world.fx_eur_dkk_fixed".

## Returns

Fact: id, value, status (verified, VERIFY, synthetic or proposed) and file of the fact.

## Raises

FactNotFound: the id is unknown. The message names up to three close ids.

## Example

```python
>>> from halvaro.core import fact
>>> f = fact("world.fx_eur_dkk_fixed")
>>> f.id, f.status in ("verified", "VERIFY", "synthetic", "proposed")
('world.fx_eur_dkk_fixed', True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
