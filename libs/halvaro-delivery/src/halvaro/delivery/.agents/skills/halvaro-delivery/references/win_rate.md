# win_rate

Module `halvaro.delivery.commercial`. Import: `from halvaro.delivery import win_rate`.

```python
win_rate(opportunity: pd.DataFrame, customer: pd.DataFrame, stage_history: pd.DataFrame | None = None, *, freq: str = 'year', by_tier: bool = True, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the win rate (won over decided) by period of the decision date and, if wanted, by customer tier.

Decided means won plus lost; withdrawn and open opportunities are not decided. Columns: [period,] [tier,] won, lost, decided, win_rate (null with nothing decided), withdrawn. `freq` is year, quarter or month; period is text (such as 2025, 2025-Q3, 2025-03). A period of 'all' is returned with freq None. With the stage history the decision date must equal the date the won or lost stage was entered, else FrameError (a mismatch is a data defect, not rounded away). A decided opportunity without a decision date is refused. A withdrawn opportunity without a decision date has no period and is left out unless freq is None.

Args:
    opportunity: The crm.opportunity frame, one row per opp_key; it needs opp_key, cus_key, stage and decision_date.
    customer: The crm.customer frame, one row per cus_key; it needs cus_key and tier.
    stage_history: Optional crm.opportunity_stage_history frame (opp_key, stage, entered_date) to check the decision date against.
    freq: The period: year, quarter, month or None for one period 'all' (default year).
    by_tier: True to split by customer tier (default), False for the period only.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with the columns period, tier (with by_tier), won, lost, decided, win_rate (rounded to 4 places) and withdrawn, sorted by period and tier.

Raises:
    FrameError: opportunity, customer or stage_history is not a DataFrame, lacks a needed column or (opportunity, customer) repeats a key; freq is not year, quarter, month or None; a decision date or entered_date is not a date or has a time zone; a won or lost opportunity has no decision date; the decision date differs from the date the decision stage was entered in the stage history; an opportunity belongs to a customer that crm.customer does not hold.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import win_rate
    >>> ctx = Context(stage="month12", role="analyst")
    >>> opp = pd.DataFrame({"opp_key": ["OPP-900001", "OPP-900002", "OPP-900003"], "cus_key": ["CUS-900001"] * 3,
    ...                     "stage": ["won", "lost", "withdrawn"], "decision_date": ["2025-03-01", "2025-04-01", "2025-05-01"]})
    >>> cust = pd.DataFrame({"cus_key": ["CUS-900001"], "tier": ["key"]})
    >>> win_rate(opp, cust, by_tier=False, context=ctx).to_dict("records")
    [{'period': '2025', 'won': 1, 'lost': 1, 'decided': 2, 'win_rate': 0.5, 'withdrawn': 1}]

## Source columns

- `crm.opportunity.opp_key`
- `crm.opportunity.cus_key`
- `crm.opportunity.stage`
- `crm.opportunity.decision_date`
- `crm.customer.cus_key`
- `crm.customer.tier`
- `crm.opportunity_stage_history.opp_key`
- `crm.opportunity_stage_history.stage`
- `crm.opportunity_stage_history.entered_date`
