# open_tenders

Module `halvaro.delivery.commercial`. Import: `from halvaro.delivery import open_tenders`.

```python
open_tenders(opportunity: pd.DataFrame, as_of: DateLike, stage_history: pd.DataFrame | None = None, *, stages: Sequence[str] = ('tender',), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the open opportunities in a tender stage on a day, with their profile, bid deadline and days to the deadline.

Each row carries the profile fields, the bid deadline, the days to it (negative when it has passed) and `deadline_passed`, the requirements and the carbon limit. `stages` (tender, PROPOSED) names the stages that count as a tender; an opportunity created after the day is not listed. `asof_exact` is false when the stage is the one stored in the release (the day is only used for the created date and the deadline); with `stage_history` (crm.opportunity_stage_history) the stage on the day is the last stage entered on or before it, an opportunity counts as open when that stage is in `stages` or any other open stage is not needed, and `asof_exact` is true. A passed deadline is flagged, never used to hide a tender.

Args:
    opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, name, cus_key, stage, is_open, project_type, country, soil_class, route_length_m, zone_key, bid_deadline, requirements, carbon_limit_kgco2e_per_m and created_date.
    as_of: The day to list the tenders for (a date, a Timestamp or an ISO text); a time of day is dropped.
    stage_history: Optional crm.opportunity_stage_history frame (opp_key, stage, entered_date, and seq when present); it gives the stage on the day.
    stages: The stage names that count as a tender, a tuple or list, not a text (default tender, PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns opp_key, name, cus_key, stage, asof_exact, project_type, country, soil_class, route_length_m, zone_key, bid_deadline, days_to_deadline, deadline_passed, requirements, carbon_limit_kgco2e_per_m, sorted by bid deadline (nulls last), then opp_key.

Raises:
    PeriodError: as_of is a number, has a time zone or is not a date.
    FrameError: opportunity or stage_history is not a DataFrame, lacks a needed column or (opportunity) repeats an opp_key; stages is a text instead of a list; is_open has nulls; bid_deadline or entered_date is not a date or has a time zone; the stage history names an opportunity that crm.opportunity does not hold.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import open_tenders
    >>> ctx = Context(stage="month12", role="analyst")
    >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002"], "name": ["Tender A", "Tender B"], "cus_key": ["CUS-900001", "CUS-900001"],
    ...                     "stage": ["tender", "won"], "is_open": [True, False], "project_type": ["district_heating", "district_heating"],
    ...                     "country": ["DK", "DK"], "soil_class": ["clay", "clay"], "route_length_m": [1200.0, 800.0], "zone_key": ["ZONE-0001", "ZONE-0001"],
    ...                     "bid_deadline": ["2025-06-30", "2025-03-01"], "requirements": [None, None], "carbon_limit_kgco2e_per_m": [None, None],
    ...                     "created_date": ["2025-01-15", "2025-01-10"]})
    >>> r = open_tenders(opp, "2025-06-01", context=ctx)
    >>> r["opp_key"].tolist()
    ['OPP-900001']
    >>> r["days_to_deadline"].tolist()
    [29]

## Source columns

- `crm.opportunity.opp_key`
- `crm.opportunity.cus_key`
- `crm.opportunity.stage`
- `crm.opportunity.is_open`
- `crm.opportunity.project_type`
- `crm.opportunity.country`
- `crm.opportunity.soil_class`
- `crm.opportunity.route_length_m`
- `crm.opportunity.bid_deadline`
- `crm.opportunity.requirements`
- `crm.opportunity.carbon_limit_kgco2e_per_m`
- `crm.opportunity.created_date`
- `crm.opportunity.name`
- `crm.opportunity.zone_key`
