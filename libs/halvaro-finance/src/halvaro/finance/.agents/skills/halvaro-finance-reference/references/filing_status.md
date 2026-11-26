# filing_status

```python
filing_status(statutory_report: pd.DataFrame, *, dk_entities: Sequence[str | None] = ('LE-01', None), context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need to know whether each annual report was filed on time, from the deadline and the filed date.

Rule: the status comes from the stored deadline: on_time when filed on or before it (whatever the time of day), late after it, not_filed without a filed date, no_deadline without a deadline. The Danish deadline rule (the fact frep.annual_reports.DK.filing_deadline_months_after_year_end, VERIFY) only checks the stored one; German entities are not checked. The envelope carries the VERIFY status.

## Args

statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, period_end, filing_deadline, filed_date and filed_on_time, one row per report.
dk_entities: The entities judged by the Danish rule, the group as None. Default LE-01 and the group (PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value has rpt_key, le_key, period_end, deadline_stored, deadline_rule, rule_agrees, filed_date, days_late (negative when early), status and filed_on_time_agrees.

## Raises

FrameError: a column is missing or a report key is repeated.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import filing_status
>>> ctx = Context(stage="month12", role="analyst")
>>> reports = pd.DataFrame({"rpt_key": ["R1", "R2"], "le_key": ["LE-01", "LE-02"], "period_end": ["2025-12-31"] * 2, "filing_deadline": ["2026-05-31"] * 2,
...                         "filed_date": ["2026-05-20", None], "filed_on_time": [True, False]})
>>> filing_status(reports, context=ctx).value[["rpt_key", "status"]].values.tolist()
[['R1', 'on_time'], ['R2', 'not_filed']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `frep.annual_reports.DK.filing_deadline_months_after_year_end`.

Source columns: `finance-reporting.statutory_report.rpt_key`, `finance-reporting.statutory_report.period_end`, `finance-reporting.statutory_report.filing_deadline`, `finance-reporting.statutory_report.filed_date`, `finance-reporting.statutory_report.le_key`, `finance-reporting.statutory_report.filed_on_time`.
