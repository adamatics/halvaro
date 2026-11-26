# prior_year_column

```python
prior_year_column(statement_line: pd.DataFrame, statutory_report: pd.DataFrame, *, codes: Sequence[str] = ('REV', 'NI', 'TA', 'EQ_TOT', 'CF_CLOSE'), tolerance: float = 0.005, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that the prior year column of each report equals the amount of the report of the year before.

Rule: for each report whose entity (or group) has a report of the year before, prior_year_amount of the lines in codes must equal that report's amount within tolerance, else prior_year_differs; a missing prior amount, or a previous report with no line or no amount, is prior_year_missing. The first report of an entity must have a null prior on lines that are not balance sheet lines, else first_year_prior. A report after a gap in the years has no previous report and is not checked. The five default lines and the tolerance are proposed business choices.

## Args

statement_line: Frame finance-reporting.statement_line with rpt_key, statement, line_code, amount and prior_year_amount, one row per report and line code; notes rows are skipped.
statutory_report: Frame finance-reporting.statutory_report with rpt_key, le_key, scope and fiscal_year, one row per report; a group report has a null le_key.
codes: The line codes to check, a sequence of text. Default REV, NI, TA, EQ_TOT and CF_CLOSE (proposed).
tolerance: Largest accepted difference, zero or more. Default 0.005 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; the key is the report key and the line code, and the frame is empty when every prior year amount agrees.

## Raises

FrameError: a column is missing, codes is not a sequence of text, tolerance is not a number of zero or more, an rpt_key or a report line is repeated, fiscal_year is not a whole year in every row, or two reports have the same entity and fiscal year.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import prior_year_column
>>> ctx = Context(stage="month12", role="analyst")
>>> rep = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "le_key": ["LE-A", "LE-A"], "scope": ["entity", "entity"], "fiscal_year": [2024, 2025]})
>>> sl = pd.DataFrame({"rpt_key": ["R-24", "R-25"], "statement": ["income_statement"] * 2, "line_code": ["REV", "REV"], "amount": [100.0, 120.0], "prior_year_amount": [None, 90.0]})
>>> prior_year_column(sl, rep, codes=("REV",), context=ctx)[["key", "rule", "detail"]].values.tolist()
[['R-25 REV', 'prior_year_differs', 'prior 90.00, the report R-24 has 100.00']]
>>> prior_year_column(sl.assign(prior_year_amount=[None, 100.0]), rep, codes=("REV",), context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance-reporting.statement_line.rpt_key`, `finance-reporting.statement_line.line_code`, `finance-reporting.statement_line.amount`, `finance-reporting.statement_line.prior_year_amount`, `finance-reporting.statement_line.statement`, `finance-reporting.statutory_report.rpt_key`, `finance-reporting.statutory_report.le_key`, `finance-reporting.statutory_report.scope`, `finance-reporting.statutory_report.fiscal_year`.
