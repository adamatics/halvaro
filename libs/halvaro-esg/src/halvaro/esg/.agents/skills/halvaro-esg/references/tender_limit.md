# tender_limit

Module `halvaro.esg.data_requests`. Import: `from halvaro.esg import tender_limit`.

```python
tender_limit(R: pd.DataFrame, CL: pd.DataFrame | None = None, OT: pd.DataFrame | None = None, *, request_type: str = 'tender_requirement', context: halvaro.core.access.Context) -> list[TenderLimit]
```

Use this when you need the carbon limit and due date of each tender requirement, checked against the crm side.

The tender requirement rows of R (request_type 'tender_requirement', PROPOSED) as TenderLimit. `CL` is the delivery customer_carbon_limit frame (opp_key and limit_kgco2e_per_m or
carbon_limit_kgco2e_per_m), `OT` the delivery open_tenders frame (opp_key, bid_deadline). A limit or a due date that differs from the crm side is reported in `warnings` and never corrected; without CL or
OT the row is returned with a warning that it was not cross-checked. A tender row without an opp_key or a limit raises FrameError.

Args:
    R: The energy-esg.esg_data_request table with the columns cus_key, request_no (one row per customer and request number), received, due, answered_date, request_type, opp_key and limit_kgco2e_per_m.
    CL: The delivery customer_carbon_limit frame with opp_key (one row per opportunity) and limit_kgco2e_per_m or carbon_limit_kgco2e_per_m, and optionally cus_key; None to skip that check.
    OT: The delivery open_tenders frame with opp_key (one row per opportunity) and bid_deadline; None to skip that check.
    request_type: The request_type that marks a tender requirement (PROPOSED: tender_requirement).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A list of TenderLimit tuples, one per tender row of R in the order of R, with cus_key, request_no, opp_key, limit_kgco2e_per_m, due, crm_limit and bid_deadline (null when the crm side gives none), limit_agrees and due_agrees (null when not checked) and warnings (a tuple of texts, empty when everything agrees); empty when R has no tender row.

Raises:
    FrameError: R is not a frame or lacks a needed column (including request_type, opp_key and limit_kgco2e_per_m); R has two rows for a customer and request number; a date column holds numbers, a value that is not a date, no received or due date, or a due date before the received date.
    FrameError: a tender row has no opp_key or no limit.
    FrameError: CL lacks opp_key or both limit columns, or OT lacks opp_key or bid_deadline; CL or OT has more than one row for an opportunity.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import tender_limit
    >>> ctx = Context(stage="month12", role="analyst")
    >>> R = pd.DataFrame({
    ...     "cus_key": ["CUS-900001"], "request_no": [2], "received": ["2031-03-10"], "due": ["2031-04-10"], "answered_date": [None],
    ...     "request_type": ["tender_requirement"], "opp_key": ["OPP-900001"], "limit_kgco2e_per_m": [12.5]})
    >>> CL = pd.DataFrame({"opp_key": ["OPP-900001"], "limit_kgco2e_per_m": [12.5]})
    >>> OT = pd.DataFrame({"opp_key": ["OPP-900001"], "bid_deadline": ["2031-04-10"]})
    >>> t = tender_limit(R, CL, OT, context=ctx)
    >>> [(x.opp_key, x.limit_kgco2e_per_m, x.limit_agrees, x.due_agrees, x.warnings) for x in t]
    [('OPP-900001', 12.5, True, True, ())]
    >>> tender_limit(R, context=ctx)[0].warnings
    ('not cross-checked against the crm side',)

## Source columns

- `energy-esg.esg_data_request.cus_key`
- `energy-esg.esg_data_request.request_no`
- `energy-esg.esg_data_request.received`
- `energy-esg.esg_data_request.due`
- `energy-esg.esg_data_request.answered_date`
- `energy-esg.esg_data_request.status`
- `energy-esg.esg_data_request.request_type`
- `energy-esg.esg_data_request.opp_key`
- `energy-esg.esg_data_request.limit_kgco2e_per_m`
- `crm.opportunity.carbon_limit_kgco2e_per_m`
- `crm.opportunity.bid_deadline`
