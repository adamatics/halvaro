# statements_check

```python
statements_check(statement_line: pd.DataFrame, *, tolerance: float = 0.011, link_tolerance: float = 0.005, footing: Mapping[str, Any] = {'GP': ('REV', 'OOI', 'COS', 'EXT'), 'EBIT': ('GP', 'STAFF', 'DEP', 'OOE'), 'PBT': ('EBIT', 'DIV', 'FININC', 'FINEXP'), 'NI': ('PBT', 'TAX'), 'FA_TOT': ('FA_TANG', 'FA_INV', 'GRPLOAN', 'DTA'), 'CA_TOT': ('INVT', 'CONTR_A', 'TRADE_R', 'OTH_R', 'GRP_R', 'PREP', 'CASH'), 'TA': ('FA_TOT', 'CA_TOT'), 'EQ_TOT': ('EQ_SC', 'EQ_RE', 'EQ_BF', 'EQ_YR'), 'PROV_TOT': ('PROV',), 'LT_TOT': ('DEBT_GRP_LT',), 'CL_TOT': ('TRADE_P', 'CONTR_L', 'GRP_P', 'TAX_P', 'OTH_P'), 'LIAB_TOT': ('LT_TOT', 'CL_TOT'), 'TEL': ('EQ_TOT', 'PROV_TOT', 'LIAB_TOT'), 'CF_OPS': ('CF_EBIT', 'CF_DEP', 'CF_GAIN', 'CF_PROV', 'CF_INVT', 'CF_CONTR', 'CF_TRADE_R', 'CF_OTH_R', 'CF_GRP', 'CF_TRADE_P', 'CF_OTH_P'), 'CF_OPA': ('CF_OPS', 'CF_FININC', 'CF_FINEXP', 'CF_DIV'), 'CF_INVA': ('CF_CAPEX_T', 'CF_PROCEEDS'), 'CF_FINA': ('CF_EQ',), 'CF_NET': ('CF_OPA', 'CF_INVA', 'CF_FINA'), 'CF_CLOSE': ('CF_NET', 'CF_OPEN'), 'OPEN_TOT': ('OPEN_SC', 'OPEN_RE'), 'DIVPAID_TOT': ('DIVPAID_SC', 'DIVPAID_RE'), 'RESULT_TOT': ('RESULT_SC', 'RESULT_RE'), 'CLOSE_TOT': ('CLOSE_SC', 'CLOSE_RE')}, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check a set of statutory statements for lines that do not foot and links that do not hold, per report.

Rule: foot (a subtotal or total equals the sum of its components in the footing table; components a report lacks count for nothing), balance_sheet_balances (TA equals TEL), cash_flow_ends_at_cash (CF_CLOSE equals CASH), equity_ends_at_balance_sheet (CLOSE_TOT equals EQ_TOT), equity_result_is_net_income (RESULT_TOT equals NI), equity_rolls (CLOSE_TOT equals OPEN_TOT plus DIVPAID_TOT plus RESULT_TOT, a missing DIVPAID_TOT counting as zero), cash_flow_opens_at_prior_cash (CF_OPEN equals the prior year CASH) and null_amount (a watched line with a null amount). Notes rows are skipped. For EBIT, when GP is missing or null, EBIT foots against REV, OOI, COS, EXT, STAFF, DEP and OOE (the German layout). The tolerances and the footing table are proposed business choices.

## Args

statement_line: Frame finance-reporting.statement_line with rpt_key, statement, line_no, line_code, amount, prior_year_amount and line_type, one row per report and line code.
tolerance: Largest accepted difference when a line foots, zero or more. Default 0.011 (proposed).
link_tolerance: Largest accepted difference for the links, the equity roll and the opening cash, zero or more. Default 0.005 (proposed).
footing: Mapping from a subtotal line code to the tuple of its component codes. Default the footing table of the nine reports (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; the key is the report key and the line code, and the frame is empty when every check holds.

## Raises

FrameError: a column is missing, tolerance or link_tolerance is not a number of zero or more, footing is not a mapping, amount or prior_year_amount holds text that is not a number, a row has no rpt_key, or a report has more than one row for a line code.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import statements_check
>>> ctx = Context(stage="month12", role="analyst")
>>> sl = pd.DataFrame({"rpt_key": ["R-1", "R-1"], "statement": ["balance_sheet"] * 2, "line_no": [1, 2], "line_code": ["TA", "TEL"], "amount": [100.0, 90.0], "prior_year_amount": [None, None], "line_type": ["total"] * 2})
>>> statements_check(sl, context=ctx)[["key", "rule", "detail"]].values.tolist()
[['R-1 TA', 'balance_sheet_balances', 'TA 100.00 against TEL 90.00']]
>>> statements_check(sl.assign(amount=[100.0, 100.0]), context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance-reporting.statement_line.rpt_key`, `finance-reporting.statement_line.statement`, `finance-reporting.statement_line.line_no`, `finance-reporting.statement_line.line_code`, `finance-reporting.statement_line.amount`, `finance-reporting.statement_line.prior_year_amount`, `finance-reporting.statement_line.line_type`.
