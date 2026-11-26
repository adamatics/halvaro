# customer_carbon_limit

Module `halvaro.delivery.commercial`. Import: `from halvaro.delivery import customer_carbon_limit`.

```python
customer_carbon_limit(opportunity: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the customer carbon limit per route metre of the opportunities that state one.

Only opportunities with a limit are returned. No bid deadline is given here: ask open_tenders. A limit of zero or less, or a limit on a row without a customer, is refused.

Args:
    opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, carbon_limit_kgco2e_per_m and route_length_m.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns opp_key, cus_key, carbon_limit_kgco2e_per_m, route_length_m, sorted by opp_key; no rows when no opportunity states a limit.

Raises:
    FrameError: opportunity is not a DataFrame, lacks a needed column or repeats an opp_key; a carbon limit is zero or below; a carbon limit stands on an opportunity without a customer.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import customer_carbon_limit
    >>> ctx = Context(stage="month12", role="analyst")
    >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002"], "cus_key": ["CUS-900001", "CUS-900001"],
    ...                     "carbon_limit_kgco2e_per_m": [80.0, None], "route_length_m": [1000.0, 500.0]})
    >>> r = customer_carbon_limit(opp, context=ctx)
    >>> r["opp_key"].tolist(), r["carbon_limit_kgco2e_per_m"].tolist()
    (['OPP-900001'], [80.0])

## Source columns

- `crm.opportunity.opp_key`
- `crm.opportunity.cus_key`
- `crm.opportunity.carbon_limit_kgco2e_per_m`
- `crm.opportunity.route_length_m`
