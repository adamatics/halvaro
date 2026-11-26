# size_class

```python
size_class(statutory_report: pd.DataFrame, *, dk_entities: Sequence[str | None] = ('LE-01', None), context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need how many of the three Danish size criteria a report exceeds: revenue, balance sheet total and average employees.

Rule: each value is compared with the threshold of its fact (all VERIFY, the envelope carries that status); a value above the threshold exceeds it, a value at the threshold does not. Only the entities in dk_entities are judged; the others are listed with empty criteria (no German thresholds are a fact). The reporting class is not derived here.

## Args

statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, revenue, total_assets, average_employees and size_criteria_met.
dk_entities: The entities judged, the group as None. Default LE-01 and the group (PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value has rpt_key, le_key, revenue_over, assets_over, employees_over, criteria_exceeded, size_criteria_met (stored) and agrees (empty when the stored count is empty).

## Raises

FrameError: a column is missing, or a judged report has no number in revenue, total assets or employees.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import size_class
>>> ctx = Context(stage="month12", role="analyst")
>>> reports = pd.DataFrame({"rpt_key": ["R1", "R2"], "le_key": ["LE-01"] * 2, "revenue": [0, 10 ** 13], "total_assets": [0, 10 ** 13], "average_employees": [0, 10 ** 6], "size_criteria_met": [0, 3]})
>>> size_class(reports, context=ctx).value[["rpt_key", "criteria_exceeded", "agrees"]].values.tolist()
[['R1', 0.0, True], ['R2', 3.0, True]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `frep.annual_reports.DK.size_thresholds.net_revenue`, `frep.annual_reports.DK.size_thresholds.balance_sheet_total`, `frep.annual_reports.DK.size_thresholds.average_full_time_employees`.

Source columns: `finance-reporting.statutory_report.rpt_key`, `finance-reporting.statutory_report.le_key`, `finance-reporting.statutory_report.revenue`, `finance-reporting.statutory_report.total_assets`, `finance-reporting.statutory_report.average_employees`, `finance-reporting.statutory_report.size_criteria_met`.
