# scope3_coverage

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import scope3_coverage`.

```python
scope3_coverage(L: pd.DataFrame, screening: Mapping[str, Any] | None = None, year: int | None = None, basis: str = 'current', *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need to see which of the 15 scope 3 categories have lines and the reason for each absent one.

The 15 scope 3 categories against the lines: present or not, kgco2e, and the reason for an absent one from the screening decision. `screening` maps a category to the reason it is out (for example
{'3.2': 'screened out: capital goods are in 3.1'}); an absent category without an entry has the reason 'not screened: decision needed'. PROPOSED: no default screening
(policy.esg.scope3_screening is needed). A reason given for a category that has lines is ignored with a warning.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    screening: Mapping from a scope 3 category (such as '3.2') to the reason it is out, or None for no screening.
    year: The whole year, like 2025; the year before the year of world.now when None.
    basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with ghg_category, present, n_lines, kgco2e and reason (null for a present category), one row for each of the 15 categories in order.

Raises:
    FrameError: screening is not a mapping or names something that is not a scope 3 category, L is not a frame or lacks a column, is_superseded has nulls, a line key is repeated, kgco2e is null, year is not a whole year between 1900 and 2100, basis is not current or first_booked, a scope is not 1, 2 or 3, a scope 3 line has no ghg_category or one that is not among the 15, a scope 2 line has a method other than location or market, or on the current basis a restated line has no supersedes_line_no or its original is not flagged is_superseded.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import scope3_coverage
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 3, "purchased_goods", 1, None, "3.1", 30.0, False, None)], columns=cols)
    >>> r = scope3_coverage(L, {"3.2": "screened out: capital goods are in 3.1"}, 2025, context=ctx)
    >>> int(r.value["present"].sum()), len(r.value)
    (1, 15)
    >>> r.value.set_index("ghg_category").loc[["3.2", "3.3"], "reason"].tolist()
    ['screened out: capital goods are in 3.1', 'not screened: decision needed']

## Source columns

- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.method`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
