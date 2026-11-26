# profile_rules

Module `halvaro.delivery.comparables`. Import: `from halvaro.delivery import profile_rules`.

```python
profile_rules(*, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the named profiles of the comparable rule as a table, to see which filters each profile applies.

One row per profile with the filter fields (null where the profile does not filter), require_route_length (False: only a profile with a route window needs the length) and status proposed (policy.delivery.comparable_rule is needed).

Args:
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per profile and the columns profile, country, type, soil_class, status, route_min_m, route_max_m, start_from, end_from, require_route_length and rule_status ("proposed").

Raises:
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import profile_rules
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rules = profile_rules(context=ctx)
    >>> "de_clay_window" in rules["profile"].tolist()
    True
    >>> set(rules["rule_status"])
    {'proposed'}

## Source columns

- `projects.project.prj_key`
