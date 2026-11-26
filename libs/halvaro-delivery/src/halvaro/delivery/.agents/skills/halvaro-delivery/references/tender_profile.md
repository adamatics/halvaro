# tender_profile

Module `halvaro.delivery.commercial`. Import: `from halvaro.delivery import tender_profile`.

```python
tender_profile(opportunity: pd.DataFrame, opp_key: str, *, context: halvaro.core.access.Context) -> pd.Series
```

Use this when you need one opportunity as the profile that is the input of comparable_set.

Fields: opp_key, cus_key, type (the project type), country, soil_class, route_length_m, bid_deadline. The row is a Series, nothing is searched here. For the comparable set pass `{'country': row.country, 'type': row.type, 'soil_class': row.soil_class, ...}` as a profile mapping (a route window around the length is a caller's choice). A null length stays null.

Args:
    opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, project_type, country, soil_class, route_length_m and bid_deadline.
    opp_key: The key of the opportunity as one text, for example OPP-900001.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A Series with the index opp_key, cus_key, type, country, soil_class, route_length_m and bid_deadline (a Timestamp, or NaT when there is none).

Raises:
    FrameError: opportunity is not a DataFrame, lacks a needed column or repeats an opp_key; opp_key is not a single text; the opportunity is not in crm.opportunity.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import tender_profile
    >>> ctx = Context(stage="month12", role="analyst")
    >>> opp = pd.DataFrame({"opp_key": ["OPP-900001"], "cus_key": ["CUS-900001"], "project_type": ["district_heating"], "country": ["DK"],
    ...                     "soil_class": ["clay"], "route_length_m": [1200.0], "bid_deadline": ["2025-06-30"]})
    >>> row = tender_profile(opp, "OPP-900001", context=ctx)
    >>> row["type"], row["country"], float(row["route_length_m"])
    ('district_heating', 'DK', 1200.0)

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
