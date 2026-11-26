# contingency_advice

Module `halvaro.delivery.estimating`. Import: `from halvaro.delivery import contingency_advice`.

```python
contingency_advice(overrun_dist: pd.DataFrame, shares: pd.DataFrame, lines: pd.DataFrame, *, quantile: str = 'q75', ground_causes: Sequence[str] = ('ground_conditions',), view: str = 'all_events', contingency_code: str = 'CST-830', schedule_measure: str = 'schedule', projects: Sequence[str] | None = None, context: halvaro.core.access.Context) -> ContingencyAdvice
```

Use this when you need advice on the contingency percentage of a set of projects from the ground share of delay days and the schedule overrun, net of the contingency the tender estimates already carry.

The method is the fact policy.delivery.contingency_method (the method text and its status come from the fact; the parameters below are PROPOSED): the share of delay days with a ground cause (`cause_shares`, view `all_events`, cause codes `ground_causes`) times a quantile of the schedule overrun (`overrun_distribution`, measure 'schedule', quantile q25, median or q75, PROPOSED q75), as a percentage of the contract, less the contingency the tender estimates already carry. Rows: ground_share (of delay days), schedule_overrun_<quantile> (percent), gross_percent (their product), existing_percent (median over the projects with a tender estimate of the tender line `contingency_code` over the tender total, from the `lines` of estimate_bridge with type tender; a project without the line counts as zero; 0 when no project has the line), net_percent (gross less existing, not below zero). The result states n and the number of legacy projects, and says: advice only, no percentage is hard coded, a legacy summary project has no estimate lines. Amounts of different currencies are never added: the existing share is a ratio per project. `projects` limits the lines to a set (a comparable set); without it every project of the lines frame counts.

Args:
    overrun_dist: The output of overrun_distribution; it needs measure, n, n_legacy and the column of `quantile`, with exactly one row of `schedule_measure`.
    shares: The output of cause_shares; it needs view, cause_code and days.
    lines: The lines output of estimate_bridge; it needs prj_key, type, cst_key and amount.
    quantile: The column of the overrun distribution to use: q25, median or q75 (default q75, PROPOSED).
    ground_causes: The cause codes that count as ground causes (a tuple or list, not a text; default ground_conditions).
    view: The view of cause_shares to take the delay days from (default all_events).
    contingency_code: The cost code of the contingency line of the tender estimate (default CST-830).
    schedule_measure: The measure name of the schedule row in overrun_dist (default schedule).
    projects: Optional prj_key values (a list) that limit the lines to a set.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A ContingencyAdvice (named tuple): rows (a DataFrame with measure, value, unit and note for ground_share, schedule_overrun_<quantile>, gross_percent, existing_percent and net_percent), n (projects behind the schedule overrun), n_legacy (how many of them are legacy summary projects), method (text, PROPOSED) and caveats (a tuple of texts; advice only).

Raises:
    FrameError: quantile is not q25, median or q75; a frame is not a DataFrame or lacks a needed column; ground_causes is a text instead of a list; overrun_dist does not have exactly one row of schedule_measure; shares has no rows for the view; the delay days of the view are zero; the schedule overrun quantile is null; projects is a text instead of a list.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import contingency_advice
    >>> ctx = Context(stage="month12", role="analyst")
    >>> dist = pd.DataFrame({"measure": ["schedule"], "n": [4], "n_legacy": [1], "q75": [0.2]})
    >>> shares = pd.DataFrame({"view": ["all_events", "all_events"], "cause_code": ["ground_conditions", "weather"], "days": [30, 10]})
    >>> lines = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "type": ["tender", "tender"], "cst_key": ["CST-830", "CST-100"], "amount": [5.0, 95.0]})
    >>> r = contingency_advice(dist, shares, lines, context=ctx)
    >>> r.rows.set_index("measure")["value"].to_dict()
    {'ground_share': 0.75, 'schedule_overrun_q75': 20.0, 'gross_percent': 15.0, 'existing_percent': 5.0, 'net_percent': 10.0}
    >>> (r.n, r.n_legacy)
    (4, 1)

## Source columns

- `projects.delay_event.cause_code`
- `projects.delay_event.days`
- `projects.estimate_line.cst_key`
- `projects.estimate_line.amount`
- `projects.estimate_version.type`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `policy.delivery.contingency_method`
