# comparable_set

Module `halvaro.delivery.comparables`. Import: `from halvaro.delivery import comparable_set`.

```python
comparable_set(project: pd.DataFrame, profile: str | Mapping[str, Any] = 'de_clay_window', *, exclude: Sequence[str] = (), require_route_length: bool = False, as_of: dt.date | None = None, overrides: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> ComparableSet
```

Use this when you need the comparable projects of a named profile (or your own rule) on a date, with a count of what each filter removed.

Returns the projects of a profile on a date (default: the release date world.now), sorted by prj_key. Status is computed from the dates on the date. A null route length stays in the set with route_known false, unless the rule has a route window
or require_route_length is on (then the project is dropped as no_route_length). `dropped` counts the projects each filter removed, in the order country, type, soil_class, no_start_date, status, no_route_length, route_window, start_before_window,
end_before_window, excluded; nothing is dropped without a count. A project without a start date has no status and no start window: it is dropped as no_start_date when the rule has a status or start_from (after the country, type and soil filters,
so a null start of a project outside the cell does not matter), and kept when the rule has neither. The profile table is PROPOSED (policy.delivery.comparable_rule is needed).

Args:
    project: The projects.project frame, one row per prj_key; it needs prj_key, country, type, soil_class, route_length_m (numeric), legacy, data_depth, start and actual_end.
    profile: A name of PROFILES (see profile_rules) or a mapping of filter fields (country, type, soil_class, status, route_min_m, route_max_m, start_from, end_from, require_route_length). A rule status is one text or a list of texts (planned, active, completed).
    exclude: Project keys to leave out (for example the project under review); one key as text is accepted.
    require_route_length: True drops the projects without a route length as no_route_length.
    as_of: The date on which the status is computed; None means the release date (fact world.now).
    overrides: A mapping of filter fields that replaces single fields of the profile.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ComparableSet: frame (prj_key, route_length_m, legacy, data_depth, route_known; sorted by prj_key), rule (the rule applied, with require_route_length and as_of as an ISO text), dropped (the count each filter removed, in the order they ran) and profile (the profile name used; None for a mapping without one).

Raises:
    FrameError: project is not a DataFrame, has duplicate column names, lacks a needed column, has an index named like a column or a text route_length_m; a prj_key is null or repeated; a project has no start date where the rule needs one and its status cannot be computed; a date column is unreadable; profile is neither a known name nor a mapping; exclude is not a list of keys; the rule has an unknown field, a non-numeric route bound, a non-text value, an unknown status, a date that is not a date, or route_min_m above route_max_m; overrides is not a mapping.
    PeriodError: as_of is a number, is not a date or has a time zone.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import comparable_set
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900002", "PRJ-900003"], "country": ["DE", "DE", "DK"],
    ...                     "type": ["dh_network"] * 3, "soil_class": ["clay"] * 3, "route_length_m": [5000.0, 9000.0, 5000.0],
    ...                     "legacy": [False, False, True], "data_depth": ["full", "full", "summary"],
    ...                     "start": ["2029-01-01"] * 3, "actual_end": ["2029-06-01"] * 3})
    >>> res = comparable_set(prj, "de_clay_window", as_of="2030-01-01", context=ctx)
    >>> res.frame["prj_key"].tolist()
    ['PRJ-900001']
    >>> res.dropped
    {'country': 1, 'route_window': 1}
    >>> res.profile
    'de_clay_window'

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
