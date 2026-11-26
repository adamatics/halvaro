# order_book_check

```python
order_book_check(order_intake_backlog: pd.DataFrame, *, tolerance: float = 0.05, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check the order book of each entity and project type: the closing backlog is the opening plus order intake less revenue recognised, and the opening is the previous closing.

Rule: roll_forward when the closing differs from opening plus intake less revenue by more than tolerance (default 0.05, proposed); opening_not_previous_closing when the opening differs from the closing of the month before by more than the same tolerance. Book to bill is not tied.

## Args

order_intake_backlog: Frame finance.order_intake_backlog with le_key, project_type, period, backlog_opening, order_intake_total, revenue_recognised and backlog_closing, no missing months.
tolerance: Largest accepted difference, zero or more, in the unit of the backlog columns. Default 0.05 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; empty when the order book is clean.

## Raises

FrameError: a column is missing, tolerance is not a number of zero or more, a value is null, a key and period is repeated, or a month is skipped within an entity and project type.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import order_book_check
>>> ctx = Context(stage="month12", role="analyst")
>>> book = pd.DataFrame({"le_key": ["LE-01"] * 2, "project_type": ["dh_network"] * 2, "period": ["2026-01", "2026-02"], "backlog_opening": [100.0, 150.0],
...                      "order_intake_total": [80.0, 40.0], "revenue_recognised": [30.0, 40.0], "backlog_closing": [150.0, 160.0]})
>>> order_book_check(book, context=ctx)[["key", "rule"]].values.tolist()
[['LE-01 dh_network 2026-02', 'roll_forward']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.order_intake_backlog.le_key`, `finance.order_intake_backlog.project_type`, `finance.order_intake_backlog.period`, `finance.order_intake_backlog.backlog_opening`, `finance.order_intake_backlog.order_intake_total`, `finance.order_intake_backlog.revenue_recognised`, `finance.order_intake_backlog.backlog_closing`.
