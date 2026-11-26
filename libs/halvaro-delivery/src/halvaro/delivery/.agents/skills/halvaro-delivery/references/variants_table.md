# variants_table

Module `halvaro.delivery.comparables`. Import: `from halvaro.delivery import variants_table`.

```python
variants_table(project: pd.DataFrame, rules: Mapping[str, Mapping[str, Any]] | None = None, *, metric: pd.DataFrame | None = None, as_of: dt.date | None = None, default: str = 'de_clay_window', exclude: Sequence[str] = (), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need to compare how many projects, how many legacy projects and what metric median each comparable rule gives, the default profile first.

One row per rule, the default profile first: n projects, legacy count and share, and, when a metric frame (prj_key, value) is passed, metric_n (projects with a value), metric_missing (without one) and metric_median.
`rules` maps a name to a rule (filter fields as in a profile); when it is None every named profile is listed. An override rule of the same name as a profile replaces it. `exclude` removes the project(s) under review from every rule (as in comparable_set).
A rule may give a project count one above the count of the matching variant in the esg truth; that is not a defect when the extra project is a planned one without a purchase footprint.
The count 24 of the esg variant dk_all_status_start_2024_on against 23 in the esg truth is such a case (kept because tests/test_comparables.py pins it; review item 8 of #440).

Args:
    project: The projects.project frame, one row per prj_key; it needs prj_key, country, type, soil_class, route_length_m (numeric), legacy, data_depth, start and actual_end.
    rules: A mapping of rule name to a mapping of filter fields, or None for every named profile.
    metric: A frame with prj_key (one row per project) and a numeric value column, or None for no metric columns.
    as_of: The date on which the status is computed; None means the release date (fact world.now).
    default: The name of the rule listed first; a name of PROFILES or a key of rules.
    exclude: Project keys to leave out of every rule; one key as text is accepted.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with one row per rule, the default first: rule, n, legacy_n, legacy_share (NaN when n is 0) and, with a metric frame, metric_n, metric_missing and metric_median.

Raises:
    FrameError: project is not a DataFrame, has duplicate column names, lacks a needed column or has a text route_length_m; a prj_key is null or repeated; rules is not a mapping or a rule is not a mapping of valid filter fields (as comparable_set raises); metric is not a DataFrame, lacks prj_key or value, has a non-numeric value or more than one row for a project; default is neither a profile nor a rule; exclude is not a list of keys.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import variants_table
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "country": ["DE", "DE", "DK"],
    ...                     "type": ["dh_network"] * 3, "soil_class": ["clay"] * 3, "route_length_m": [5000.0, 6000.0, 5000.0],
    ...                     "legacy": [False, True, False], "data_depth": ["full", "summary", "full"],
    ...                     "start": ["2029-01-01"] * 3, "actual_end": ["2029-06-01"] * 3})
    >>> met = pd.DataFrame({"prj_key": ["PRJ-900001"], "value": [10.0]})
    >>> out = variants_table(prj, {"de_all": {"country": "DE"}}, metric=met, as_of="2030-01-01", default="de_all", context=ctx)
    >>> out[["rule", "n", "legacy_n", "metric_n", "metric_missing"]].to_dict("records")
    [{'rule': 'de_all', 'n': 2, 'legacy_n': 1, 'metric_n': 1, 'metric_missing': 1}]

## Source columns

- `projects.project.prj_key`
- `projects.project.country`
- `projects.project.type`
- `projects.project.soil_class`
- `projects.project.route_length_m`
- `projects.project.legacy`
- `projects.project.data_depth`
- `projects.project.start`
- `projects.project.actual_end`
