# Reference of the other functions of halvaro-finance, flat reference

# approval_limit_breaches

```python
approval_limit_breaches(purchase_order: pd.DataFrame, buyer_grade: pd.DataFrame, *, limits: Sequence[tuple[Any, Any]] = ((3, 50000.0), (5, 250000.0), (None, 1000000.0)), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that the buyers of purchase orders had the authority for the value, by the grade of the buyer on the order date.

Rule: the limit depends on the grade level (PROPOSED: up to level 3 DKK 50,000, up to level 5 DKK 250,000, above DKK 1,000,000; the policy value is needed). An order above the limit of its buyer is a breach. The data has no approver, so only the buyer's authority is tested.

## Args

purchase_order: Frame procurement.purchase_order with po_key, total_value, currency, buyer_emp_key and order_date.
buyer_grade: Frame with po_key and grade_level (the level of the buyer at the order date, from halvaro-hr).
limits: A list of (grade level up to, limit in DKK) with increasing levels and None for the last step. Default PROPOSED as above.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with po_key, buyer_emp_key, order_date, grade_level, total_value_dkk, limit_dkk and breach.

## Raises

FrameError: a column is missing, po_key is not unique, limits is not a list of increasing steps ending in None, or an order has no buyer grade.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import approval_limit_breaches
>>> ctx = Context(stage="month12", role="analyst")
>>> orders = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "total_value": [60000.0, 1000.0], "currency": ["DKK"] * 2, "buyer_emp_key": ["EMP-000001"] * 2, "order_date": ["2026-01-05"] * 2})
>>> grades = pd.DataFrame({"po_key": ["PO-1", "PO-2"], "grade_level": [3, 3]})
>>> approval_limit_breaches(orders, grades, context=ctx)[["po_key", "breach"]].values.tolist()
[['PO-1', True], ['PO-2', False]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.purchase_order.po_key`, `procurement.purchase_order.total_value`, `procurement.purchase_order.currency`, `procurement.purchase_order.buyer_emp_key`, `procurement.purchase_order.order_date`.

# budget_variance

```python
budget_variance(budget_line: pd.DataFrame, cost_centre_actual: pd.DataFrame, *, version: str, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you compare what was booked with what was budgeted, by entity, cost centre, account and period, for one budget version.

Rule: variance is actual less budget, in the entity currency and in DKK; amounts keep the ledger sign (debit positive), so a revenue variance above zero is less revenue. Only the periods of the version's lines are compared. A cell with an actual and no budget, or a budget and no actual, is listed with zero on the missing side. variance_percent is the variance over the absolute budget, empty without a budget. Variances are rounded to 2 decimals.

## Args

budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period, amount and amount_dkk.
cost_centre_actual: Frame finance.cost_centre_actual with le_key, cc_key, gl_key, period, amount and amount_dkk.
version: The budget version, for example BUD-2026.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, cc_key, gl_key, period, budget, actual, variance, variance_dkk, budget_dkk, actual_dkk and variance_percent.

## Raises

FrameError: a column is missing, the version has no lines, or a frame has more than one row for an entity, cost centre, account and period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import budget_variance
>>> ctx = Context(stage="month12", role="analyst")
>>> budget = pd.DataFrame({"le_key": ["LE-01"] * 2, "budget_version": ["BUD-2026"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6100"], "period": ["2026-01"] * 2,
...                        "amount": [100.0, 50.0], "amount_dkk": [100.0, 50.0]})
>>> actual = pd.DataFrame({"le_key": ["LE-01"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000", "GL-6200"], "period": ["2026-01"] * 2, "amount": [130.0, 20.0], "amount_dkk": [130.0, 20.0]})
>>> budget_variance(budget, actual, version="BUD-2026", context=ctx)[["gl_key", "budget", "actual", "variance"]].values.tolist()
[['GL-6000', 100.0, 130.0, 30.0], ['GL-6100', 50.0, 0.0, -50.0], ['GL-6200', 0.0, 20.0, 20.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.budget_line.le_key`, `finance.budget_line.budget_version`, `finance.budget_line.cc_key`, `finance.budget_line.gl_key`, `finance.budget_line.period`, `finance.budget_line.amount`, `finance.budget_line.amount_dkk`, `finance.cost_centre_actual.le_key`, `finance.cost_centre_actual.cc_key`, `finance.cost_centre_actual.gl_key`, `finance.cost_centre_actual.period`, `finance.cost_centre_actual.amount`, `finance.cost_centre_actual.amount_dkk`.

# committed_cost

```python
committed_cost(open_po_lines: pd.DataFrame, po_line: pd.DataFrame, purchase_order: pd.DataFrame, *, spot_orders: pd.DataFrame | None = None, delivery_type: str = 'project_site', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the value of the purchase orders that are still open, by project and cost code, in the order currency and in DKK.

Rule: the open quantity of each line (from open_po_lines and spot_orders; a line in both is counted once and flagged spot) times the unit price of its order line. Only orders of the given delivery type count (proposed "project_site"; orders for stock have no project and are dropped). DKK is converted at the booking rates.

## Args

open_po_lines: Frame from the delivery open_po_lines with po_key, line_no, prj_key and qty_open (the name remaining is also accepted).
po_line: Frame procurement.po_line with po_key, line_no, unit_price, currency and cst_key, one row per order line.
purchase_order: Frame procurement.purchase_order with po_key and delivery_type, one row per order.
spot_orders: Frame from the delivery spot_orders with the same columns as open_po_lines. Optional.
delivery_type: The delivery type of the orders that count. Default "project_site" (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, cst_key, currency, spot, n_lines, committed and committed_dkk, sorted by project, cost code, currency and spot.

## Raises

FrameError: a column is missing, po_line or purchase_order repeats a key, an order line is listed twice, a quantity is null or negative, an open line has no order line or no price or currency, a quantity or a price is infinite, belongs to an order without a delivery type, or (of the counted type) has no project, or qty_open and remaining disagree.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import committed_cost
>>> ctx = Context(stage="month12", role="analyst")
>>> open_lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "prj_key": ["PRJ-1"], "qty_open": [4.0]})
>>> lines = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "unit_price": [25.0], "currency": ["DKK"], "cst_key": ["CST-1"]})
>>> orders = pd.DataFrame({"po_key": ["PO-1"], "delivery_type": ["project_site"]})
>>> committed_cost(open_lines, lines, orders, context=ctx)[["prj_key", "cst_key", "spot", "committed_dkk"]].values.tolist()
[['PRJ-1', 'CST-1', False, 100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `procurement.po_line.po_key`, `procurement.po_line.line_no`, `procurement.po_line.unit_price`, `procurement.po_line.currency`, `procurement.po_line.cst_key`, `procurement.purchase_order.po_key`, `procurement.purchase_order.delivery_type`.

# contract_position

```python
contract_position(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need revenue recognised less billed on each project row, split into the contract asset and the contract liability.

Rule: the position is revenue_recognised less billed. A positive position is the contract asset (wip, GL-2100), a negative one the contract liability (GL-4500, shown as a positive amount).

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value and billed, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, revenue_recognised, billed, contract_position (asset positive, liability negative), wip and contract_liability, on the index of the frame.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import contract_position
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "billed": [300.0, 700.0],
...                    "actual_cost": [400.0, 400.0], "eac": [800.0, 800.0]})
>>> contract_position(pf, {}, cap=0.95, context=ctx)[["prj_key", "contract_position", "wip", "contract_liability"]].to_dict("records")
[{'prj_key': 'PRJ-1', 'contract_position': 200.0, 'wip': 200.0, 'contract_liability': 0.0}, {'prj_key': 'PRJ-2', 'contract_position': -200.0, 'wip': 0.0, 'contract_liability': 200.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`, `finance.project_financials.contract_value`, `finance.project_financials.billed`.

# cost_centre_team_map

```python
cost_centre_team_map(cost_centre: pd.DataFrame, team: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that finance cost centres and hr teams point at each other.

Rule: finance.cost_centre.team_key and hr.team.cost_centre_key are compared both ways. A cost centre without a team key (overhead) is not a violation.

## Args

cost_centre: Frame finance.cost_centre with cc_key and team_key, one row per cost centre.
team: Frame hr.team with team_key and cost_centre_key, one row per team.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail: cost_centre_without_team (a team key that hr does not have), team_without_cost_centre (an hr team whose cost centre finance does not have) and cost_centre_team_mismatch (the two views name different partners); empty when they agree.

## Raises

FrameError: a column is missing or a frame has more than one row for a key.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_centre_team_map
>>> ctx = Context(stage="month12", role="analyst")
>>> cost_centre = pd.DataFrame({"cc_key": ["CC-1", "CC-2"], "team_key": ["TEAM-1", "TEAM-9"]})
>>> team = pd.DataFrame({"team_key": ["TEAM-1", "TEAM-2"], "cost_centre_key": ["CC-1", "CC-3"]})
>>> cost_centre_team_map(cost_centre, team, context=ctx)[["key", "rule"]].values.tolist()
[['CC-2', 'cost_centre_without_team'], ['TEAM-2', 'team_without_cost_centre']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.cost_centre.cc_key`, `finance.cost_centre.team_key`, `hr.team.team_key`, `hr.team.cost_centre_key`.

# cost_per_metre_by_cost_code

```python
cost_per_metre_by_cost_code(comparable_set: pd.DataFrame, project_cost_breakdown: pd.DataFrame, project: pd.DataFrame, route_change: pd.DataFrame | None = None, *, context: <class 'halvaro.core.access.Context'>) -> CostPerMetre
```

Use this when you compare projects by actual cost per metre of route for each cost code, with the median over the projects.

Rule: per project and cost code the last breakdown row (the latest period) gives the cost at completion, which is the cost to date for an active project; it is divided by the route length in metres and rounded to four decimals. The median per code is taken over the projects, per currency. A project with no breakdown row, or without a route length above zero, is left out and listed in dropped, never estimated; a code a project has no row for is left out of that code's median, not counted as zero. An as-built length above zero replaces the planned length and is flagged in route_source. The as-built column is a stand-in (proposed).

## Args

comparable_set: Frame of the projects to compare with prj_key and legacy (and data_depth if present), one row per project.
project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
project: Frame projects.project with prj_key and route_length_m, one row per project.
route_change: Optional frame with prj_key and as_built_length_m, one row per project; a missing or non positive length keeps the planned one. Default None.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

CostPerMetre, a named tuple of three frames: by_code with cst_key, currency, n_projects and median_per_metre; per_project with prj_key, cst_key, currency, cost_at_completion, route_length_m, per_metre, route_source (as_built or planned) and legacy; dropped with prj_key and reason (no finance rows or no route length).

## Raises

FrameError: a column is missing, actual_amount, route_length_m or as_built_length_m holds text that is not a number, a period is not text like 2026-01, a breakdown value is null, a breakdown row is repeated for a project, period and cost code, a project has more than one currency, a key is repeated in the comparable set, projects or route_change, or a project of the comparable set is not in projects.project.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_per_metre_by_cost_code
>>> ctx = Context(stage="month12", role="analyst")
>>> cs = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "legacy": [False, False, False]})
>>> pr = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-B", "PRJ-C"], "route_length_m": [100.0, 200.0, 50.0]})
>>> cb = pd.DataFrame({"prj_key": ["PRJ-A", "PRJ-A", "PRJ-B"], "period": ["2026-01", "2026-02", "2026-02"], "cst_key": ["CST-1"] * 3, "currency": ["DKK"] * 3,
...                    "actual_amount": [500.0, 1000.0, 3000.0], "incurred_in_period": [500.0, 500.0, 3000.0], "estimate_amount": [1200.0, 1200.0, 3200.0]})
>>> res = cost_per_metre_by_cost_code(cs, cb, pr, context=ctx)
>>> res.per_project[["prj_key", "per_metre"]].values.tolist()
[['PRJ-A', 10.0], ['PRJ-B', 15.0]]
>>> res.by_code[["cst_key", "n_projects", "median_per_metre"]].values.tolist()
[['CST-1', 2, 12.5]]
>>> res.dropped.values.tolist()
[['PRJ-C', 'no finance rows']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_cost_breakdown.prj_key`, `finance.project_cost_breakdown.period`, `finance.project_cost_breakdown.cst_key`, `finance.project_cost_breakdown.currency`, `finance.project_cost_breakdown.actual_amount`, `finance.project_cost_breakdown.incurred_in_period`, `finance.project_cost_breakdown.estimate_amount`, `projects.project.prj_key`, `projects.project.route_length_m`.

# cost_to_completion

```python
cost_to_completion(project_financials: pd.DataFrame, prj_keys: str | Sequence[str], period: str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the cost still to come on a list of projects in one period: EAC less actual cost, with the committed cost shown apart.

Rule: cost_to_completion is EAC less actual cost and uncommitted is that less the committed cost, both to two decimals. Amounts stay in the currency of the row and are never summed across currencies. A project without a row in the period is listed with the reason "no finance row".

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, eac, actual_cost and committed_cost, one row per project and period.
prj_keys: The projects, one key or a list of keys, each at most once.
period: The period, text like 2026-03.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, currency, eac, actual_cost, cost_to_completion, committed_cost, uncommitted and reason, one row per key in the order given.

## Raises

FrameError: a column is missing, a period is not text like 2026-03, a key is repeated, or the frame has two rows for a project in the period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import cost_to_completion
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["DKK"], "eac": [800.0], "actual_cost": [400.0], "committed_cost": [100.0]})
>>> r = cost_to_completion(pf, ["PRJ-1", "PRJ-9"], "2026-03", context=ctx).set_index("prj_key")
>>> r[["cost_to_completion", "uncommitted"]].loc["PRJ-1"].to_dict(), r.loc["PRJ-9", "reason"]
({'cost_to_completion': 400.0, 'uncommitted': 300.0}, 'no finance row')
>>> cost_to_completion(pf, ["PRJ-1"], "2026-3", context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: period must be text like 2025-11, not '2026-3'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.committed_cost`, `finance.project_financials.currency`.

# dkk_amount

```python
dkk_amount(amount: pd.Series, currency: pd.Series, *, basis: str, fx_rate: pd.DataFrame | None = None, on: pd.Series | None = None, group: bool = False, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need amounts in DKK to the cent: on the booking basis with the fixed rates of core, or on the daily basis with the latest rate on or before each date.

Rule: rounding is half away from zero on the cent. The daily basis needs one date per amount and a rate frame without duplicate (currency, rate_date), and is refused for group statements. A currency without a rate is an error.

## Args

amount: The amounts.
currency: The currency of each amount, same length, no nulls.
basis: "booking" or "daily".
fx_rate: Frame finance.fx_rate; on the booking basis it must agree with core for the currencies used. Optional.
on: The date of each amount; required on the daily basis.
group: True for group statements, which use the booking basis only.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series of the amounts in DKK, on the index of amount.

## Raises

BasisError: the basis is neither booking nor daily, or the daily basis is asked for a group statement.
FrameError: amount and currency differ in length or have nulls, a rate frame lacks a column or disagrees with core, a currency has no rate, or the daily basis lacks its dates or rates.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import dkk_amount
>>> ctx = Context(stage="month12", role="analyst")
>>> from halvaro.core import fact
>>> rate = fact("world.fx_eur_dkk_fixed").value
>>> dkk_amount(pd.Series([10.0, 10.0]), pd.Series(["DKK", "EUR"]), basis="booking", context=ctx).tolist() == [10.0, round(10 * rate, 2)]
True
>>> dkk_amount(pd.Series([1.0]), pd.Series(["DKK"]), basis="spot", context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.BasisError: basis 'spot' is not available; use 'booking' or 'daily'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `finance.fx_rate.currency`, `finance.fx_rate.rate`, `finance.fx_rate.booking_rate`, `finance.fx_rate.rate_date`.

# eliminations

```python
eliminations(consolidation_entry: pd.DataFrame, group_trial_balance: pd.DataFrame | None = None, *, tolerance: float = 0.011, period_tolerance: float = 0.5, required_types: tuple[str, ...] = ('investment', 'ic_loan', 'ic_trade_revenue'), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need to check the consolidation entries of the group: that they are positive, balanced, between two different accounts, complete by type, and zero over a period.

Rule: every violation is listed. non_positive_amount: an amount that is not above zero. entry_unbalanced: a stored difference above tolerance. same_account: an entry that debits and credits the same account of the same entity. entry_type_missing: a type of required_types without an entry (PROPOSED investment, ic_loan, ic_trade_revenue). period_not_zero: with the group trial balance, the eliminations of a period that do not sum to zero within period_tolerance. The entries are not recomputed from the books of the entities.

## Args

consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk, one row per year, period and entry number.
group_trial_balance: Optional frame with period, gl_key and elimination_dkk; when given, the eliminations of each period are checked to sum to zero.
tolerance: Largest accepted stored difference of an entry in DKK (default 0.011).
period_tolerance: Largest accepted sum of the eliminations of a period in DKK (default 0.5).
required_types: The entry types that must each have an entry (default investment, ic_loan, ic_trade_revenue, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with the columns table, key, rule and detail; empty when the entries are clean.

## Raises

FrameError: a column is missing, an entry number is repeated within a year and period, or a tolerance is negative or not a number.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import eliminations
>>> ctx = Context(stage="month12", role="analyst")
>>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
>>> eliminations(entry, context=ctx)[["key", "rule"]].to_dict("records")
[{'key': 'ic_loan', 'rule': 'entry_type_missing'}, {'key': 'ic_trade_revenue', 'rule': 'entry_type_missing'}]
>>> eliminations(entry.assign(difference_dkk=5.0), required_types=("investment",), context=ctx)[["key", "rule"]].to_dict("records")
[{'key': '2026-03 #1', 'rule': 'entry_unbalanced'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance-reporting.consolidation_entry.fiscal_year`, `finance-reporting.consolidation_entry.period`, `finance-reporting.consolidation_entry.entry_no`, `finance-reporting.consolidation_entry.entry_type`, `finance-reporting.consolidation_entry.basis`, `finance-reporting.consolidation_entry.debit_le_key`, `finance-reporting.consolidation_entry.debit_gl_key`, `finance-reporting.consolidation_entry.credit_le_key`, `finance-reporting.consolidation_entry.credit_gl_key`, `finance-reporting.consolidation_entry.amount_dkk`, `finance-reporting.consolidation_entry.difference_dkk`, `finance-reporting.group_trial_balance.period`, `finance-reporting.group_trial_balance.elimination_dkk`.

# employer_oncosts

```python
employer_oncosts(gross: pd.DataFrame, *, country_of: dict[str, str], base: str = 'gross_plus_overtime', context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the employer pension and social contributions on gross pay, per entity, cost centre and month, by country.

Rule: each contribution is the share of its fact (fin.payroll_on_costs.<country>.employer_pension_share and employer_social_share, VERIFY) times the base amount, rounded to the cent with halves away from zero. The base_amount is rounded to two decimals with numpy round (halves to even). The base amount is the gross salary plus overtime (a null or missing overtime counts as zero), or the gross salary alone with base "gross". Holiday pay is not computed.

## Args

gross: Frame with le_key, cc_key, period and gross_salary, and optionally overtime, one row per entity, cost centre and month.
country_of: Dict from every le_key of the frame to its country, DK or DE; it selects the two shares.
base: "gross_plus_overtime" (gross salary plus overtime) or "gross" (gross salary only). Default "gross_plus_overtime".
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, cc_key, period, base_amount, employer_pension and employer_social, sorted by le_key, cc_key and period; the envelope carries the facts used and their VERIFY status.

## Raises

FrameError: a column is missing, gross_salary or overtime holds text that is not a number, gross_salary has a null, a row is repeated for an entity, cost centre and month, base is not one of the two names, or country_of is not a dict that maps every le_key of the frame to DK or DE.
FactNotFound: a share fact is not in the fact set; the facts of both DK and DE are read, so a missing DE fact raises it even when every entity is Danish.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import employer_oncosts
>>> ctx = Context(stage="month12", role="analyst")
>>> gross = pd.DataFrame({"le_key": ["LE-A"], "cc_key": ["CC-1"], "period": ["2026-01"], "gross_salary": [1000.0], "overtime": [100.0]})
>>> out = employer_oncosts(gross, country_of={"LE-A": "DK"}, context=ctx).value
>>> out.columns.tolist()
['le_key', 'cc_key', 'period', 'base_amount', 'employer_pension', 'employer_social']
>>> out["base_amount"].tolist()
[1100.0]
>>> employer_oncosts(gross, country_of={"LE-A": "DK"}, base="gross", context=ctx).value["base_amount"].tolist()
[1000.0]
>>> employer_oncosts(gross, country_of={"LE-A": "DK"}, base="net", context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: base is 'gross_plus_overtime' or 'gross'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.payroll_on_costs.DK.employer_pension_share`, `fin.payroll_on_costs.DE.employer_pension_share`, `fin.payroll_on_costs.DK.employer_social_share`, `fin.payroll_on_costs.DE.employer_social_share`.

Source columns: `finance.payroll_summary.le_key`, `finance.payroll_summary.cc_key`, `finance.payroll_summary.period`, `finance.payroll_summary.component`, `finance.payroll_summary.amount`.

# exposure_bridge

```python
exposure_bridge(open_exposure_result: pd.DataFrame, finance_exposure_result: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need to explain the gap between the open quantity and the finance definitions of the price exposure, per project.

Rule: difference is the finance exposure less the open exposure. received_or_timing_dkk is the finance exposure less the open purchase order part (what finance counts on lines already received or booked in another month) and reserved_dkk is what only the open definition counts. By construction difference equals received_or_timing_dkk less reserved_dkk, to the cent. A project in one result only is listed with 0 on the other side.

## Args

open_exposure_result: The result of open_exposure, with prj_key, exposure_po_dkk, exposure_reserved_dkk and exposure_dkk, one row per project.
finance_exposure_result: The result of finance_exposure, with prj_key and price_exposure_dkk, one row per project.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, open_po_dkk, open_reserved_dkk, open_dkk, finance_dkk, difference, received_or_timing_dkk and reserved_dkk, sorted by project.

## Raises

FrameError: a column is missing, a result has more than one row for a project, or an amount is null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import exposure_bridge
>>> ctx = Context(stage="month12", role="analyst")
>>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_po_dkk": [10.0], "exposure_reserved_dkk": [4.0], "exposure_dkk": [14.0]})
>>> finance = pd.DataFrame({"prj_key": ["PRJ-1"], "price_exposure_dkk": [30.0]})
>>> exposure_bridge(opened, finance, context=ctx)[["difference", "received_or_timing_dkk", "reserved_dkk"]].values.tolist()
[[16.0, 20.0, 4.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.price_exposure`, `procurement.po_line.received_qty`, `inventory.reservation.qty_open`.

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

# finance_exposure

```python
finance_exposure(project_financials: pd.DataFrame, period: str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the price exposure of the projects at a period as the finance data defines it: the cumulative exposure and the part that can be recovered.

Rule: the rows of the period with a price exposure or a recoverable amount different from zero are taken from finance.project_financials and converted to DKK at the booking rates. The open quantity definition of the exposure is a different figure.

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, price_exposure and price_recoverable, one row per project and period.
period: The period, text like 2026-03.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, currency, price_exposure, price_recoverable, price_exposure_dkk and price_recoverable_dkk; empty when no project has a non-zero row in the period.

## Raises

FrameError: a column is missing or a project has more than one row in the period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import finance_exposure
>>> ctx = Context(stage="month12", role="analyst")
>>> projects = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-03"], "currency": ["EUR"], "price_exposure": [100.0], "price_recoverable": [40.0]})
>>> finance_exposure(projects, "2026-03", context=ctx)[["prj_key", "price_exposure", "price_recoverable"]].values.tolist()
[['PRJ-1', 100.0, 40.0]]
>>> finance_exposure(projects, "2026-04", context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.currency`, `finance.project_financials.price_exposure`, `finance.project_financials.price_recoverable`.

# forecast_vs_budget

```python
forecast_vs_budget(forecast_line: pd.DataFrame, forecast_version: pd.DataFrame, budget_line: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you compare each forecast version with the budget it is based on, by entity, cost centre, account and period in DKK.

Rule: difference is forecast less the budget of the version the forecast version names; a cell without a budget has budget 0; the difference is rounded to 2 decimals. basis_ok says that the line follows its version: actual up to actuals_through_period, projected after.

## Args

forecast_line: Frame finance.forecast_line with le_key, forecast_version, cc_key, gl_key, period, amount_dkk and basis.
forecast_version: Frame finance.forecast_version with forecast_version, actuals_through_period and budget_version.
budget_line: Frame finance.budget_line with le_key, budget_version, cc_key, gl_key, period and amount_dkk.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with forecast_version, le_key, cc_key, gl_key, period, basis, forecast_dkk, budget_dkk, difference_dkk and basis_ok.

## Raises

FrameError: a column is missing, a table has more than one row for its key, or a forecast version is not in the version table.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import forecast_vs_budget
>>> ctx = Context(stage="month12", role="analyst")
>>> forecast = pd.DataFrame({"le_key": ["LE-01"] * 2, "forecast_version": ["FC-1"] * 2, "cc_key": ["CC-1"] * 2, "gl_key": ["GL-6000"] * 2, "period": ["2026-01", "2026-02"],
...                          "amount_dkk": [110.0, 120.0], "basis": ["actual", "projected"]})
>>> versions = pd.DataFrame({"forecast_version": ["FC-1"], "actuals_through_period": ["2026-01"], "budget_version": ["BUD-2026"]})
>>> budget = pd.DataFrame({"le_key": ["LE-01"], "budget_version": ["BUD-2026"], "cc_key": ["CC-1"], "gl_key": ["GL-6000"], "period": ["2026-01"], "amount_dkk": [100.0]})
>>> forecast_vs_budget(forecast, versions, budget, context=ctx)[["period", "forecast_dkk", "budget_dkk", "difference_dkk", "basis_ok"]].values.tolist()
[['2026-01', 110.0, 100.0, 10.0, True], ['2026-02', 120.0, 0.0, 120.0, True]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.forecast_line.le_key`, `finance.forecast_line.forecast_version`, `finance.forecast_line.cc_key`, `finance.forecast_line.gl_key`, `finance.forecast_line.period`, `finance.forecast_line.amount_dkk`, `finance.forecast_line.basis`, `finance.forecast_version.forecast_version`, `finance.forecast_version.actuals_through_period`, `finance.forecast_version.budget_version`, `finance.budget_line.le_key`, `finance.budget_line.budget_version`, `finance.budget_line.cc_key`, `finance.budget_line.gl_key`, `finance.budget_line.period`, `finance.budget_line.amount_dkk`.

# group_trial_balance

```python
group_trial_balance(journal_line: pd.DataFrame, reporting_adjustment: pd.DataFrame, consolidation_entry: pd.DataFrame, *, opening_sources: tuple[str, ...] = ('opening',), context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the movement of the group per period and account in DKK: the two entities plus the reporting adjustments plus the eliminations.

Rule: the movement of an entity is the sum of the DKK amounts of its journal lines in the period, as booked (not the change of translated closing balances). Lines of the opening journals (source in opening_sources) are not movement. adjustment_dkk is debit less credit. elimination_dkk is the debit side of the entries positive and the credit side negative; entries on the opening balance basis act on opening balances and are left out. An account whose movement is eliminated to zero is listed with zero. Opening and closing balances and the year end roll are not rebuilt.

## Args

journal_line: Frame finance.journal_line with le_key, period, gl_key, amount_dkk and source.
reporting_adjustment: Frame finance-reporting.reporting_adjustment with period, gl_key, debit_dkk and credit_dkk.
consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk.
opening_sources: The journal sources that are opening balances and not movement (default "opening").
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with period, gl_key, le01_movement_dkk, le02_movement_dkk, adjustment_dkk, elimination_dkk and movement_dkk (their sum), sorted by period and account.

## Raises

FrameError: a column is missing, an amount_dkk is null, or the lines name an entity other than LE-01 and LE-02.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import group_trial_balance
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01", "LE-02"], "period": ["2026-03"] * 2, "gl_key": ["GL-8000"] * 2, "amount_dkk": [100.0, -40.0], "source": ["manual"] * 2})
>>> adjustment = pd.DataFrame({"period": ["2026-03"], "gl_key": ["GL-8000"], "debit_dkk": [10.0], "credit_dkk": [0.0]})
>>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
>>> group_trial_balance(lines, adjustment, entry, context=ctx).value[["gl_key", "adjustment_dkk", "elimination_dkk", "movement_dkk"]].to_dict("records")
[{'gl_key': 'GL-8000', 'adjustment_dkk': 10.0, 'elimination_dkk': 100.0, 'movement_dkk': 170.0}, {'gl_key': 'GL-8100', 'adjustment_dkk': 0.0, 'elimination_dkk': -100.0, 'movement_dkk': -100.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.period`, `finance.journal_line.gl_key`, `finance.journal_line.amount_dkk`, `finance.journal_line.source`, `finance-reporting.reporting_adjustment.period`, `finance-reporting.reporting_adjustment.gl_key`, `finance-reporting.reporting_adjustment.debit_dkk`, `finance-reporting.reporting_adjustment.credit_dkk`.

# intercompany_match

```python
intercompany_match(match: pd.DataFrame, *, tolerance_dkk: float = 1.0, eur_rate: float | None = None, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the intercompany pairs of the two legal entities recomputed and compared with what is stored.

Rule: difference_dkk is the amount booked by LE-01 less the amount booked by LE-02 in DKK. status is matched when the difference is within tolerance_dkk (PROPOSED 1.0, the group tolerance of the plan) and difference otherwise. fx_ok is true when the EUR amount of LE-02 at the fixed rate is within 0.011 of its DKK amount. agrees is true when the recomputed status and difference equal the stored ones.

## Args

match: Frame finance-reporting.intercompany_match with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, amount_le02_eur, difference_dkk and status, one row per ic_ref.
tolerance_dkk: Largest difference in DKK that still counts as matched (default 1.0, PROPOSED).
eur_rate: The EUR to DKK rate; without it the fixed rate of the fact world.fx_eur_dkk_fixed is used and listed in the envelope.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, difference_dkk, status, stored_status, fx_ok and agrees.

## Raises

FrameError: a column is missing, an ic_ref is empty or repeated, tolerance_dkk is negative or not a number, or eur_rate is not a positive number.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import intercompany_match
>>> ctx = Context(stage="month12", role="analyst")
>>> match = pd.DataFrame({"ic_ref": ["IC-1", "IC-2"], "kind": ["loan", "trade"], "period": ["2026-03"] * 2, "amount_le01_dkk": [1000.0, 500.0],
...                       "amount_le02_dkk": [1000.0, 498.0], "amount_le02_eur": [100.0, 49.8], "difference_dkk": [0.0, 2.0], "status": ["matched", "difference"]})
>>> result = intercompany_match(match, eur_rate=10.0, context=ctx)
>>> result.value[["ic_ref", "difference_dkk", "status", "fx_ok", "agrees"]].to_dict("records")
[{'ic_ref': 'IC-1', 'difference_dkk': 0.0, 'status': 'matched', 'fx_ok': True, 'agrees': True}, {'ic_ref': 'IC-2', 'difference_dkk': 2.0, 'status': 'difference', 'fx_ok': True, 'agrees': True}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `finance-reporting.intercompany_match.ic_ref`, `finance-reporting.intercompany_match.amount_le01_dkk`, `finance-reporting.intercompany_match.amount_le02_dkk`, `finance-reporting.intercompany_match.amount_le02_eur`, `finance-reporting.intercompany_match.difference_dkk`, `finance-reporting.intercompany_match.status`.

# journal_integrity

```python
journal_integrity(journal_header: pd.DataFrame, journal_line: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you check the journals of the ledger: every journal has its lines, balances to the cent and is numbered without gaps.

Rule: the checks are orphan_lines, header_without_lines, line_count, duplicate_header, duplicate_line, unbalanced_local and unbalanced_dkk (to the cent), numbering_gap (gapless per entity, as the numbering fact says), unknown_currency and dkk_conversion (the DKK amount of a line is the rounded fixed rate conversion, except one residual line per journal).

## Args

journal_header: Frame finance.journal_header with le_key, journal_no and line_count.
journal_line: Frame finance.journal_line with le_key, journal_no, line_no, amount, amount_dkk and currency.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame of violations with the columns table, key, rule and detail; empty when the ledger is clean.

## Raises

FrameError: a column is missing, a journal has no le_key or journal_no, or the numbering fact names a rule other than gapless_per_entity.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import journal_integrity
>>> ctx = Context(stage="month12", role="analyst")
>>> header = pd.DataFrame({"le_key": ["LE-01"], "journal_no": [1], "line_count": [3]})
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": [1, 1], "line_no": [1, 2], "amount": [10.0, -10.0], "amount_dkk": [10.0, -10.0], "currency": ["DKK"] * 2})
>>> journal_integrity(header, lines, context=ctx).value["rule"].tolist()
['line_count']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.bookkeeping.journal_numbering`, `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: `finance.journal_header.le_key`, `finance.journal_header.journal_no`, `finance.journal_header.line_count`, `finance.journal_line.le_key`, `finance.journal_line.journal_no`, `finance.journal_line.line_no`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`, `finance.journal_line.currency`.

# labour_absorption_check

```python
labour_absorption_check(journal_line: pd.DataFrame, *, project_labour: str = 'GL-6100', project_absorbed: str = 'GL-7900', service_absorbed: str = 'GL-7910', service_accounts: tuple[str, ...] = ('GL-6610', 'GL-6620'), max_warranty_share: float = 0.2, tolerance: float = 0.005, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that labour booked on projects and on service is absorbed in the ledger, per entity and month for projects and over the whole window for service.

Rule: for each entity and month, the lines on project_labour and project_absorbed must net to zero within tolerance, else the violation project_labour_not_absorbed. Over the whole window and all entities, the service labour (the lines on service_accounts) must be covered by the credit on service_absorbed, and the absorbed amount may exceed it by at most max_warranty_share of itself (the rest is the warranty ticket charge), else the violation service_labour_not_absorbed. The service sums use amount_dkk when the frame has it, otherwise amount. Amounts are in currency units and summed in whole cents; the tolerance is cut down to whole cents. All keyword defaults are proposed business choices (accounts, share and tolerance).

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, period and amount, and optionally amount_dkk and currency, one row per line.
project_labour: Account of project labour at standard rate. Default GL-6100 (proposed).
project_absorbed: Account of labour absorbed to projects. Default GL-7900 (proposed).
service_absorbed: Account of labour absorbed to service. Default GL-7910 (proposed).
service_accounts: Accounts of service labour, as a tuple. Default GL-6610 and GL-6620 (proposed).
max_warranty_share: Largest share of the absorbed service amount that may exceed the service labour, from 0 to below 1. Default 0.2 (proposed).
tolerance: Largest accepted difference in currency units, zero or more. Default 0.005 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail: project_labour_not_absorbed (key is the entity and month; the net amount is written in the detail text, not in a column) and service_labour_not_absorbed (key is "window"); empty when the labour is absorbed.

## Raises

FrameError: a column is missing, an amount is null, an le_key is null, an amount is text that is not a number, max_warranty_share is not a number from 0 to below 1, tolerance is not a number of zero or more, service_accounts is a string, or the service lines are in more than one currency while the frame has no amount_dkk.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import labour_absorption_check
>>> ctx = Context(stage="month12", role="analyst")
>>> jl = pd.DataFrame({"le_key": ["LE-A"] * 4, "period": ["2026-01"] * 4, "gl_key": ["GL-6100", "GL-7900", "GL-6610", "GL-7910"], "amount": [1000.0, -900.0, 100.0, -100.0]})
>>> labour_absorption_check(jl, context=ctx)[["key", "rule", "detail"]].values.tolist()
[['LE-A 2026-01', 'project_labour_not_absorbed', 'GL-6100 and GL-7900 net to 100.00, not zero']]
>>> labour_absorption_check(jl.assign(amount=[1000.0, -1000.0, 100.0, -100.0]), context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`.

# labour_cost_overrun

```python
labour_cost_overrun(project_cost_breakdown: pd.DataFrame, project_budget_line: pd.DataFrame, cost_code: pd.DataFrame, window_start: dt.date | str | pd.Timestamp, window_end: dt.date | str | pd.Timestamp, *, active_only: bool = True, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you rank projects by how far their labour cost has run over the labour budget in a window of months.

Rule: labour is every leaf cost code (not a group) of category labour. Per project, in its own currency: labour_budget is the sum of the budget lines of the original (lowest) budget version, labour_estimate the latest estimate at completion, labour_actual_to_date the cumulative actual at the last period up to the window end, and labour_actual_window the cost incurred in the window. overrun_vs_budget_pct is actual to date over budget less 100, and overrun_vs_estimate_pct is the same against the estimate; both compare cost to date with the whole budget or estimate, so they understate a project that has only started. A project without labour budget is listed with null percentages and the reason "no labour budget". Rows are sorted by overrun_vs_budget_pct, largest first; the estimate percent is a second measure that can rank the projects differently, so say which measure a ranking uses. The definition of the overrun is a business choice (proposed).

## Args

project_cost_breakdown: Frame finance.project_cost_breakdown with prj_key, period (text like 2026-01), cst_key, currency, actual_amount, incurred_in_period and estimate_amount, one row per project, period and cost code.
project_budget_line: Frame finance.project_budget_line with prj_key, cst_key, budget_version, budget_amount and currency.
cost_code: Frame projects.cost_code with cst_key, category and is_group, one row per cost code.
window_start: First month of the window, a month text like 2026-01 or a date.
window_end: Last month of the window, in the same forms.
active_only: True keeps the projects with labour cost incurred in the window; False lists every project with cost up to the window end. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, currency, labour_budget, labour_estimate, labour_actual_to_date, labour_actual_window, overrun_vs_budget_pct, overrun_vs_estimate_pct and reason.

## Raises

FrameError: a column is missing, a window bound is not a month, the window starts after it ends, a period is not text like 2026-01, a value is null where one is needed, a key is repeated, a project has more than one currency, a cost code of the breakdown is not in cost_code, cost_code has no labour leaf, or a budget is in another currency than the cost rows.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import labour_cost_overrun
>>> ctx = Context(stage="month12", role="analyst")
>>> costs = pd.DataFrame({"prj_key": ["PRJ-1"], "period": ["2026-01"], "cst_key": ["CST-L"], "currency": ["EUR"], "actual_amount": [120.0], "incurred_in_period": [120.0], "estimate_amount": [130.0]})
>>> budget = pd.DataFrame({"prj_key": ["PRJ-1"], "cst_key": ["CST-L"], "budget_version": [1], "budget_amount": [100.0], "currency": ["EUR"]})
>>> codes = pd.DataFrame({"cst_key": ["CST-L"], "category": ["labour"], "is_group": [False]})
>>> labour_cost_overrun(costs, budget, codes, "2026-01", "2026-01", context=ctx)[["prj_key", "labour_budget", "labour_actual_to_date", "overrun_vs_budget_pct"]].values.tolist()
[['PRJ-1', 100.0, 120.0, 20.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_cost_breakdown.prj_key`, `finance.project_cost_breakdown.period`, `finance.project_cost_breakdown.cst_key`, `finance.project_cost_breakdown.currency`, `finance.project_cost_breakdown.actual_amount`, `finance.project_cost_breakdown.incurred_in_period`, `finance.project_cost_breakdown.estimate_amount`, `finance.project_budget_line.prj_key`, `finance.project_budget_line.cst_key`, `finance.project_budget_line.budget_version`, `finance.project_budget_line.budget_amount`, `finance.project_budget_line.currency`, `projects.cost_code.cst_key`, `projects.cost_code.category`, `projects.cost_code.is_group`.

# ledger_gross_pay

```python
ledger_gross_pay(journal_line: pd.DataFrame, *, accounts: tuple[str, ...] = ('GL-7000', 'GL-7005', 'GL-7050'), context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the gross salary booked in the ledger per legal entity, cost centre and month, to tie out against the payroll summary.

Rule: the sum of the journal lines on the salary accounts, in the currency of the entity, debit positive, to the cent. The default accounts GL-7000, GL-7005 and GL-7050 are PROPOSED until fin.payroll_on_costs.gross_salary_accounts is a fact.

## Args

journal_line: Frame finance.journal_line with le_key, cc_key, gl_key, period and amount.
accounts: The salary accounts (default GL-7000, GL-7005 and GL-7050, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, cc_key, period and ledger_gross_pay, sorted by those three columns.

## Raises

FrameError: a column is missing, accounts is not a non-empty tuple of account keys, or a line on these accounts has no cost centre, entity or period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import ledger_gross_pay
>>> ctx = Context(stage="month3", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 3, "cc_key": ["CC-1"] * 3, "gl_key": ["GL-7000", "GL-7005", "GL-6000"], "period": ["2026-03"] * 3, "amount": [1000.5, 200.25, 50.0]})
>>> ledger_gross_pay(lines, context=ctx).to_dict("records")
[{'le_key': 'LE-01', 'cc_key': 'CC-1', 'period': '2026-03', 'ledger_gross_pay': 1200.75}]
>>> ledger_gross_pay(lines.assign(cc_key=[None, "CC-1", "CC-1"]), context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: gross salary lines without a cost centre, entity or period; the tie-out is per cost centre
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.cc_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`.

# loss_provision

```python
loss_provision(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need the provision for the loss that a project is expected to make: the part of the expected loss not yet recognised.

Rule: the expected loss is the EAC above the contract value (zero when the EAC is not above it). The provision is the expected loss times one less the cost to cost fraction, rounded to two decimals; none when the project has ended.

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named loss_provision, on the index of the frame, in the contract currency of the row; zero where no loss is expected.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import loss_provision
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "contract_value": [1000.0] * 3,
...                    "actual_cost": [400.0, 600.0, 1200.0], "eac": [800.0, 1200.0, 1200.0]})
>>> loss_provision(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
[0.0, 100.0, 0.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`, `finance.project_financials.contract_value`.

# manual_journals

```python
manual_journals(journal_header: pd.DataFrame, journal_line: pd.DataFrame, *, gl_key: str | None = None, prj_key: str | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the lines of the journals that were posted by hand, optionally only those on one account or one project.

Rule: the journals whose header source is manual; their lines with the date and description of the header.

## Args

journal_header: Frame finance.journal_header with le_key, journal_no, source, posting_date and description.
journal_line: Frame finance.journal_line with le_key, journal_no, line_no, gl_key, prj_key, amount, amount_dkk and currency.
gl_key: Keep only the lines on this account. Optional.
prj_key: Keep only the lines on this project. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, journal_no, line_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk of each line.

## Raises

FrameError: a column is missing or a manual journal is listed twice in the header frame.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import manual_journals
>>> ctx = Context(stage="month12", role="analyst")
>>> header = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": [1, 2], "source": ["manual", "auto"], "posting_date": ["2026-03-01"] * 2, "description": ["x", "y"]})
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 4, "journal_no": [1, 1, 2, 2], "line_no": [1, 2, 1, 2], "gl_key": ["GL-1", "GL-2"] * 2, "prj_key": [None] * 4,
...                       "amount": [10.0, -10.0, 5.0, -5.0], "amount_dkk": [10.0, -10.0, 5.0, -5.0], "currency": ["DKK"] * 4})
>>> manual_journals(header, lines, context=ctx)[["journal_no", "gl_key", "amount"]].values.tolist()
[[1, 'GL-1', 10.0], [1, 'GL-2', -10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_header.le_key`, `finance.journal_header.journal_no`, `finance.journal_header.source`, `finance.journal_header.posting_date`, `finance.journal_header.description`, `finance.journal_line.le_key`, `finance.journal_line.journal_no`, `finance.journal_line.line_no`, `finance.journal_line.gl_key`, `finance.journal_line.prj_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`, `finance.journal_line.currency`.

# margin_trail

```python
margin_trail(project_financials: pd.DataFrame, prj_key: str, write_down: pd.DataFrame | None = None, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you follow the margin of one project period by period, with the period and amount of its write-down. For the margins alone, of all projects at once, project_margin is enough.

Rule: the rows of the project in period order, with margin_pct and forecast_margin_pct as in project_margin. Each write-down journal line is put on the period of its posting month: write_down_period is true there, and write_down_amount (entity currency) and write_down_amount_dkk add up the lines of that month to two decimals; elsewhere they are empty. The amounts stay in the currency of the rows and are never summed across currencies.

## Args

project_financials: Frame finance.project_financials with prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
prj_key: The project key.
write_down: The output of write_down_journal with posting_date, amount and amount_dkk (and currency if present). Default None, no write-down.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with period, currency, margin_pct, forecast_margin_pct, write_down_period, write_down_amount and write_down_amount_dkk, one row per period of the project.

## Raises

FrameError: prj_key, period, currency, contract_value, eac, actual_cost, revenue_recognised or loss_provision is missing, the project has no row, a posting date is missing or not a date, an amount is null, a period is repeated for the project (checked only when write_down is given), the write-down is in another currency than the rows, or the write-down is posted in a month without a row of the project.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import margin_trail
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-1"], "period": ["2026-02", "2026-03"], "currency": ["EUR", "EUR"], "contract_value": [1000.0, 1000.0], "eac": [800.0, 800.0],
...                    "actual_cost": [300.0, 400.0], "revenue_recognised": [400.0, 500.0], "loss_provision": [0.0, 0.0]})
>>> wd = pd.DataFrame({"posting_date": ["2026-03-15"], "amount": [40.0], "amount_dkk": [300.0]})
>>> margin_trail(pf, "PRJ-1", wd, context=ctx)[["period", "margin_pct", "forecast_margin_pct", "write_down_period", "write_down_amount_dkk"]].to_dict("records")
[{'period': '2026-02', 'margin_pct': 25.0, 'forecast_margin_pct': 20.0, 'write_down_period': False, 'write_down_amount_dkk': nan}, {'period': '2026-03', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0, 'write_down_period': True, 'write_down_amount_dkk': 300.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.contract_value`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.revenue_recognised`, `finance.project_financials.loss_provision`.

# mgmt_pl_check

```python
mgmt_pl_check(mgmt_pl_department: pd.DataFrame, trial_balance: pd.DataFrame, *, result_accounts: tuple[int, int] = (5100, 8999), revenue_accounts: tuple[int, int] = (5100, 5499), tolerance: float = 1.0, line_tolerance: float = 0.05, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check that the management P&L agrees with the ledger and adds up within each department row.

Rule: per entity and month, the operating result of the management P&L must equal the ledger result (credit less debit on the result accounts) and the total revenue must equal the ledger revenue (the revenue accounts), each within tolerance. Per department row, the cost lines must add up to total_cost and revenue less cost must equal the operating result, each within line_tolerance. The account ranges and tolerances are business choices (proposed).

## Args

mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, total_revenue, total_cost, operating_result and the ten cost line columns, one row per entity, department and period.
trial_balance: Frame finance.trial_balance with le_key, period, gl_key (like GL-5100), debit and credit.
result_accounts: First and last account number of the result accounts. Default (5100, 8999) (proposed).
revenue_accounts: First and last account number of the revenue accounts. Default (5100, 5499) (proposed).
tolerance: Largest accepted gap per entity and month. Default 1.0 (proposed).
line_tolerance: Largest accepted gap per department row. Default 0.05 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame of violations with table, key, rule and detail; the rules are result_differs_from_ledger, revenue_differs_from_ledger, cost_lines_do_not_add_up and result_not_revenue_less_cost. Empty when everything agrees.

## Raises

FrameError: a column is missing, a tolerance is negative or not a number, an account range is not a (first, last) pair, or a row is repeated for an entity, department and period.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import mgmt_pl_check
>>> ctx = Context(stage="month12", role="analyst")
>>> costs = ["project_labour_cost", "project_other_direct_cost", "service_direct_cost", "stock_and_inventory_cost", "staff_cost", "labour_absorbed", "overhead_cost", "overhead_allocated", "depreciation_and_amortisation", "other_operating_cost"]
>>> pl = pd.DataFrame({"le_key": ["LE-01"], "dep_key": ["DEP-1"], "period": ["2026-01"], "total_revenue": [100.0], "total_cost": [60.0], "operating_result": [40.0], **{c: [0.0] for c in costs}})
>>> pl["project_labour_cost"] = 60.0
>>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-01"] * 2, "gl_key": ["GL-5100", "GL-6000"], "debit": [0.0, 60.0], "credit": [100.0, 0.0]})
>>> mgmt_pl_check(pl, tb, context=ctx).empty
True
>>> mgmt_pl_check(pl.assign(operating_result=30.0), tb, context=ctx)["rule"].tolist()
['result_differs_from_ledger', 'result_not_revenue_less_cost']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.mgmt_pl_department.le_key`, `finance.mgmt_pl_department.dep_key`, `finance.mgmt_pl_department.period`, `finance.mgmt_pl_department.total_revenue`, `finance.mgmt_pl_department.total_cost`, `finance.mgmt_pl_department.operating_result`, `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.debit`, `finance.trial_balance.credit`.

# open_exposure

```python
open_exposure(exposed_demand: pd.DataFrame, steps: pd.DataFrame, *, only_amended: bool = True, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the added cost of a price step on the demand that is still open, per project, in DKK.

Rule: the open quantity times the step of the item, converted to DKK at the booking rates and rounded to the cent. A purchase order line placed before the effective date was bought at the old price and carries no exposure. A free reservation is priced now. With only_amended the step of an ordinary price list change is not exposure, only the step of an amendment. The project set is the one of exposed_demand and is never rebuilt here.

## Args

exposed_demand: Frame with prj_key, sup_key, itm_key, qty_open (the name remaining is also accepted), source (po_line or reservation) and after_effective_date; a po_key column must be empty on reservation rows.
steps: The result of price_steps (or a frame with sup_key, itm_key, currency, step and step_percent, and optionally amended), one row per supplier and item.
only_amended: True counts only the steps of an amendment. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, n_po_lines, exposure_po_dkk, reserved_open_qty, exposure_reserved_dkk, exposure_dkk and step_percent_max (the largest step among the priced items of the project that have an open quantity, not weighted by exposure).

## Raises

FrameError: a column is missing, steps repeats a supplier and item, a demand row has a null project or quantity (or no after_effective_date on a PO line), a source is neither po_line nor reservation, a quantity is negative, a reservation has a po_key, a priced demand row has no step row or a null step, or qty_open and remaining disagree.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import open_exposure
>>> ctx = Context(stage="month12", role="analyst")
>>> demand = pd.DataFrame({"prj_key": ["PRJ-1"], "sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "qty_open": [5.0], "source": ["po_line"], "after_effective_date": [True]})
>>> steps = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "currency": ["DKK"], "step": [2.0], "step_percent": [10.0]})
>>> open_exposure(demand, steps, context=ctx)[["prj_key", "n_po_lines", "exposure_dkk"]].values.tolist()
[['PRJ-1', 1, 10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.price_list.unit_price`, `procurement.price_list.change_reason`, `procurement.price_list.valid_from`, `procurement.price_list.currency`, `procurement.po_line.qty`, `procurement.po_line.received_qty`, `inventory.reservation.qty_open`.

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

# percent_complete

```python
percent_complete(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need the percent of completion of each project row by cost to cost: actual cost over the estimate at completion.

Rule: a running project has the actual cost over the EAC, limited by cap; a project that ended on or before the end of the period has 100. The result is in percent with two decimals.

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named percent_complete, on the index of the frame, from 0 to 100.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import percent_complete
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2", "PRJ-3"], "period": ["2026-03"] * 3, "actual_cost": [400.0, 780.0, 800.0], "eac": [800.0, 800.0, 800.0]})
>>> percent_complete(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
[50.0, 95.0, 100.0]
>>> percent_complete(pf, {}, cap=1.5, context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: cap must be a number in (0, 1], ...
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`.

# price_steps

```python
price_steps(price_before: pd.DataFrame, price_after: pd.DataFrame, *, reason: str = 'framework_amendment', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the change of the price of each supplier and item between the day before an effective date and the effective date.

Rule: the two frames are joined on supplier and item. The step is the price after less the price before, and step_percent is the step over the price before in percent (four decimals; null when there is no price before or after, or when the price before is not above zero). A price counts as amended when the price in force after has the given change reason. Side says whether the item has a price on both dates, before only or after only.

## Args

price_before: Frame from price_list_on for the day before the effective date, with sup_key, itm_key, unit_price, currency and change_reason.
price_after: Frame from price_list_on for the effective date, with the same columns.
reason: The change reason that marks an amendment. Default "framework_amendment".
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, itm_key, currency, price_before, price_after, step, step_percent, amended and side (both, before_only or after_only), sorted by supplier and item.

## Raises

FrameError: a column is missing, a frame has more than one price for a supplier and item or a null price, or the currency of a price differs between the two dates.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import price_steps
>>> ctx = Context(stage="month12", role="analyst")
>>> before = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [10.0], "currency": ["EUR"], "change_reason": ["list"]})
>>> after = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "currency": ["EUR"], "change_reason": ["framework_amendment"]})
>>> price_steps(before, after, context=ctx)[["step", "step_percent", "amended", "side"]].values.tolist()
[[1.0, 10.0, True, 'both']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.price_list.unit_price`, `procurement.price_list.change_reason`, `procurement.price_list.valid_from`, `procurement.price_list.currency`.

# price_variance_report

```python
price_variance_report(supplier_invoice_line: pd.DataFrame, supplier_invoice: pd.DataFrame, *, price_steps: pd.DataFrame | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need how far the invoiced prices of each supplier and item sit from the purchase order price.

Rule: credit notes and lines without a PO price are left out. The difference of a line is (invoice price less PO price) over the PO price, in percent. Per supplier, item and currency the report gives the number of lines, the summed price variance (contract currency, to the cent) and the mean, standard deviation and largest absolute difference in percent. With a price_steps frame the step is added and step_in_variance says whether the mean difference reaches half of the step (the step sits in the PO price, so it is not in the invoice variance).

## Args

supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, itm_key, unit_price, po_unit_price, price_variance, currency and invoice_type.
supplier_invoice: Frame finance.supplier_invoice with sinv_key and sup_key, one row per invoice.
price_steps: The result of price_steps, or a frame with sup_key, itm_key and step_percent, one row per supplier and item. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, itm_key, currency, n_lines, price_variance, mean_diff_percent, sd_diff_percent and max_abs_diff_percent (and step_percent and step_in_variance with price_steps), sorted by supplier, item and currency.

## Raises

FrameError: a column is missing, supplier_invoice repeats an invoice key, an invoice line belongs to an invoice that is not in supplier_invoice, a PO price is 0, a line with a PO price has no item or currency, or price_steps repeats a supplier and item.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import price_variance_report
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"sinv_key": ["INV-1"], "itm_key": ["ITM-1"], "unit_price": [11.0], "po_unit_price": [10.0], "price_variance": [10.0], "currency": ["EUR"], "invoice_type": ["invoice"]})
>>> invoices = pd.DataFrame({"sinv_key": ["INV-1"], "sup_key": ["SUP-1"]})
>>> price_variance_report(lines, invoices, context=ctx)[["sup_key", "itm_key", "n_lines", "price_variance", "mean_diff_percent"]].values.tolist()
[['SUP-1', 'ITM-1', 1, 10.0, 10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice_line.sinv_key`, `finance.supplier_invoice_line.itm_key`, `finance.supplier_invoice_line.quantity`, `finance.supplier_invoice_line.unit_price`, `finance.supplier_invoice_line.po_unit_price`, `finance.supplier_invoice_line.price_variance`, `finance.supplier_invoice_line.currency`, `finance.supplier_invoice_line.invoice_type`, `finance.supplier_invoice.sinv_key`, `finance.supplier_invoice.sup_key`.

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

# project_margin

```python
project_margin(project_financials: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the two named margins of a project and period in percent: the margin to date and the margin forecast at completion. Never one "margin". To follow one project period by period together with its write-down, use margin_trail.

Rule: margin_pct is (revenue recognised less actual cost less loss provision) over revenue recognised, empty without revenue. forecast_margin_pct is (contract value less EAC) over contract value, empty without a contract value. Both are rounded to two decimals.

## Args

project_financials: Frame finance.project_financials with prj_key, period, contract_value, eac, actual_cost, revenue_recognised and loss_provision, one row per project and period.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, period, margin_pct and forecast_margin_pct, on the index of the frame.

## Raises

FrameError: a column is missing.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import project_margin
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-2"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "eac": [800.0, 1200.0],
...                    "actual_cost": [400.0, 600.0], "revenue_recognised": [500.0, 500.0], "loss_provision": [0.0, 100.0]})
>>> project_margin(pf, context=ctx)[["prj_key", "margin_pct", "forecast_margin_pct"]].to_dict("records")
[{'prj_key': 'PRJ-1', 'margin_pct': 20.0, 'forecast_margin_pct': 20.0}, {'prj_key': 'PRJ-2', 'margin_pct': -40.0, 'forecast_margin_pct': -20.0}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.contract_value`, `finance.project_financials.eac`, `finance.project_financials.actual_cost`, `finance.project_financials.revenue_recognised`, `finance.project_financials.loss_provision`.

# rebuild_trial_balance

```python
rebuild_trial_balance(journal_line: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, *, carry_results: bool = True, retained_earnings_gl: str = 'GL-3300', context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you need the trial balance per entity, period and account rebuilt from the journal lines and the opening items.

Rule: amounts are summed in cents. The opening journals are not movements. Balance sheet accounts run from the opening items and income statement accounts restart at each fiscal year start (there are no closing journals). With carry_results the results of earlier fiscal years sit in the retained earnings account, as in the stored table; with carry_results False they are left out (the input of roll_retained_earnings). A row exists for a non-zero opening or closing balance (also in DKK) or a non-zero movement.

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, amount, amount_dkk, currency, period (text like 2026-01) and source.
opening_balance_item: Frame finance.opening_balance_item with le_key, gl_key, amount and amount_dkk, balance sheet accounts only.
gl_account: Frame finance.gl_account with gl_key and statement (IS or BS), one row per account.
carry_results: True puts the results of earlier fiscal years in the retained earnings account. Default True.
retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame in the shape of finance.trial_balance: le_key, period, gl_key, opening_balance, debit, credit, closing_balance, currency and closing_balance_dkk.

## Raises

FrameError: a column is missing, journal_line is empty or has a line without le_key, gl_key or period, a period is not text like 2026-01, gl_account repeats an account or has a statement other than IS or BS, the retained earnings account is not a balance sheet account, an opening item is on a result account or belongs to an entity without lines, an account is not in gl_account, or an entity has more than one currency.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import rebuild_trial_balance
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 2, "gl_key": ["GL-1000", "GL-5100"], "amount": [100.0, -100.0], "amount_dkk": [100.0, -100.0], "currency": ["DKK"] * 2,
...                       "period": ["2026-01"] * 2, "source": ["manual"] * 2})
>>> opening = pd.DataFrame({"le_key": [], "gl_key": [], "amount": [], "amount_dkk": []})
>>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
>>> rebuild_trial_balance(lines, opening, accounts, context=ctx).value[["gl_key", "closing_balance"]].values.tolist()
[['GL-1000', 100.0], ['GL-5100', -100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.bookkeeping.fiscal_year_start_month`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`, `finance.journal_line.currency`, `finance.journal_line.period`, `finance.journal_line.source`, `finance.opening_balance_item.le_key`, `finance.opening_balance_item.gl_key`, `finance.opening_balance_item.amount`, `finance.opening_balance_item.amount_dkk`, `finance.gl_account.gl_key`, `finance.gl_account.statement`.

# recoverable

```python
recoverable(open_exposure_result: pd.DataFrame, terms: pd.DataFrame, contracts: pd.DataFrame, *, apply_threshold: bool = False, on: dt.date | str | pd.Timestamp | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the part of the price exposure that the customer contract passes on to the customer, per project.

Rule: exposure times the pass-through percent of the customer contract of the project, to the cent; a fixed price contract passes nothing on. The rest is absorbed. With apply_threshold (proposed False) nothing is passed on when the largest step of the project does not exceed the threshold percent of the terms; the default passes the percent on whatever the size of the step. Only the contracts of `contracts` are read from `terms`. A contract with more than one clause row needs `on`; then every used contract is read on that date and of the clauses in force the one with the latest start counts (never two).

## Args

open_exposure_result: The result of open_exposure, with prj_key, exposure_dkk and step_percent_max.
terms: Frame from price_adjustment_terms with con_key, pass_through_percent and threshold_percent (null when none), and valid_from and valid_to when a contract has several clauses.
contracts: Frame from contracts_for_project with prj_key, con_key and price_type, one row per project.
apply_threshold: True passes nothing on when step_percent_max does not exceed threshold_percent. Default False (proposed).
on: The date to read the clauses on (no time zone), needed when a contract has more than one clause row. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, con_key, price_type, exposure_dkk, pass_through_percent, threshold_percent, recoverable_dkk and absorbed_dkk, sorted by project.

## Raises

FrameError: a column is missing, contracts has more than one row for a project, a contract has several clause rows and on is missing or terms lacks valid_from and valid_to, on has a time zone, a clause has no valid_from or ends before it starts, no clause or two clauses with the same start are in force on the date, a project has no contract, a contract that is not fixed price has no terms, or a pass-through percent is outside 0 to 100.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import recoverable
>>> ctx = Context(stage="month12", role="analyst")
>>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_dkk": [1000.0], "step_percent_max": [10.0]})
>>> terms = pd.DataFrame({"con_key": ["CON-1"], "pass_through_percent": [50.0], "threshold_percent": [None]})
>>> contracts = pd.DataFrame({"prj_key": ["PRJ-1"], "con_key": ["CON-1"], "price_type": ["indexed"]})
>>> recoverable(opened, terms, contracts, context=ctx)[["prj_key", "recoverable_dkk", "absorbed_dkk"]].values.tolist()
[['PRJ-1', 500.0, 500.0]]
>>> recoverable(opened, terms, contracts.assign(price_type="fixed_price"), context=ctx)["recoverable_dkk"].tolist()
[0.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `contracts.contract.price_type`, `contracts.clause.param_value`, `contracts.clause.param2_value`.

# revenue_recognised

```python
revenue_recognised(project_financials: pd.DataFrame, actual_end: Mapping[str, Any] | pd.Series | pd.DataFrame, *, cap: float, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when you need the revenue recognised to date on each project row: the contract value times the cost to cost fraction.

Rule: the contract value in cents times the fraction of percent_complete (actual cost over EAC, limited by cap), rounded to the cent; the full contract value when the project has ended on or before the end of the period.

## Args

project_financials: Frame finance.project_financials with prj_key, period (text like 2026-03), actual_cost and eac, contract_value, one row per project and period.
actual_end: The end date of each completed project: a Series or dict from prj_key to date, or a frame with prj_key and actual_end. A project that is not in it, or has a null date, is running.
cap: The largest fraction of a running project, a number above 0 and up to 1. Required: the value of the config projects.poc_cap_before_completion.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named revenue_recognised, on the index of the frame, in the contract currency of the row.

## Raises

FrameError: a column is missing, cap is not a number in (0, 1], a period is not text like 2026-03, no key of actual_end is a prj_key of the frame, or a running project has an EAC of zero or null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import revenue_recognised
>>> ctx = Context(stage="month3", role="analyst")
>>> pf = pd.DataFrame({"prj_key": ["PRJ-1", "PRJ-3"], "period": ["2026-03"] * 2, "contract_value": [1000.0, 1000.0], "actual_cost": [400.0, 800.0], "eac": [800.0, 800.0]})
>>> revenue_recognised(pf, {"PRJ-3": "2026-02-20"}, cap=0.95, context=ctx).tolist()
[500.0, 1000.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.prj_key`, `finance.project_financials.period`, `finance.project_financials.actual_cost`, `finance.project_financials.eac`, `finance.project_financials.contract_value`.

# roll_retained_earnings

```python
roll_retained_earnings(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, *, retained_earnings_gl: str = 'GL-3300', context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when a trial balance was built without carrying results and you need the results of completed fiscal years moved into the retained earnings account.

Rule: the input is the output of rebuild_trial_balance with carry_results False. The result of a fiscal year is the sum of the closing balances of the income statement accounts at its last period, and it is added to the retained earnings account from the next fiscal year on. Only the retained earnings rows differ, and that account gets a row in every period that lacks one. The table must start at the first period of the ledger. A stored finance.trial_balance already carries the roll, so a table whose retained earnings opening balance jumps at a fiscal year start is refused instead of being rolled twice.

## Args

trial_balance: Frame with le_key, period (text like 2026-12), gl_key, opening_balance, closing_balance and closing_balance_dkk.
gl_account: Frame finance.gl_account with gl_key and statement (IS or BS).
retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is the input plus rolled_opening_balance, rolled_closing_balance and rolled_closing_balance_dkk, sorted by entity, period and account.

## Raises

FrameError: a column is missing, the retained earnings account is not a balance sheet account of gl_account, or the retained earnings opening balance jumps at a fiscal year start (the table already carries the results).
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import roll_retained_earnings
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-12", "2027-01"], "gl_key": ["GL-5100", "GL-1000"], "opening_balance": [-50.0, 0.0],
...                    "closing_balance": [-100.0, 0.0], "closing_balance_dkk": [-100.0, 0.0]})
>>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
>>> out = roll_retained_earnings(tb, accounts, context=ctx).value
>>> out[out["gl_key"] == "GL-3300"][["period", "rolled_closing_balance"]].values.tolist()
[['2026-12', 0.0], ['2027-01', -100.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.bookkeeping.fiscal_year_start_month`.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.opening_balance`, `finance.trial_balance.closing_balance`, `finance.trial_balance.closing_balance_dkk`, `finance.gl_account.gl_key`, `finance.gl_account.statement`.

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

# statement_from_ledger

```python
statement_from_ledger(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame, le_key: str, country: str, fiscal_year: int, *, require_full_year: bool = True, context: <class 'halvaro.core.access.Context'>) -> LedgerStatement
```

Use this when you rebuild the statutory lines of one entity and fiscal year from its trial balance, in the entity currency and the natural sign.

Rule: an income statement line is the movement of the year (credit less debit over the periods of the year) of the accounts mapped to it; a balance sheet line is the closing balance of the last period of the year, with the sign of the normal side of the line (credit positive). Amounts are summed in integer cents and returned in currency units (cents divided by 100, floats). In unmapped, amount_debit_positive_for_bs is credit less debit for income statement accounts and the debit positive closing balance for balance sheet accounts. The fiscal year is the calendar year. Accounts with a balance and no statutory map are returned in unmapped, and pbt is the sum of the income statement lines other than TAX; tax lines are not in the ledger accounts, so they appear as unmapped when an account carries them.

## Args

trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-03), gl_key, debit, credit and closing_balance, one row per entity, period and account.
gl_account: Frame finance.gl_account with gl_key, statement (IS or BS) and the map column of the country (dk_statutory_map or de_statutory_map).
statutory_map_line: Frame finance.statutory_map_line with map_code, line_code, statement and normal_side (debit or credit), one row per map code.
le_key: The entity.
country: DK or DE; it selects the map column of the chart of accounts.
fiscal_year: The calendar year, a whole number.
require_full_year: True demands all twelve periods of the year in the trial balance; False accepts a part year. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

LedgerStatement, a named tuple: lines (a DataFrame with map_code, line_code, statement, amount and n_accounts), unmapped (a DataFrame with gl_key, kind and amount_debit_positive_for_bs) and pbt (a number).

## Raises

FrameError: country is not DK or DE, fiscal_year is not a whole year, a column is missing, a key is repeated, an amount is null or text that is not a number, a period is null or malformed, a normal side is not debit or credit, an account is not in the chart of accounts, a statement is not IS or BS, the entity has no rows in the year or too few periods when require_full_year is true, a balance sheet account with a balance has no row in the last period, a map code is not in the map, or an account is mapped to a line of the other statement.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import statement_from_ledger
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-A", "LE-A"], "period": ["2026-01", "2026-01"], "gl_key": ["GL-4000", "GL-1000"], "debit": [0.0, 500.0], "credit": [500.0, 0.0], "closing_balance": [-500.0, 500.0]})
>>> gl = pd.DataFrame({"gl_key": ["GL-4000", "GL-1000"], "statement": ["IS", "BS"], "dk_statutory_map": ["M-REV", "M-CASH"]})
>>> ml = pd.DataFrame({"map_code": ["M-REV", "M-CASH"], "line_code": ["REV", "CASH"], "statement": ["IS", "BS"], "normal_side": ["credit", "debit"]})
>>> res = statement_from_ledger(tb, gl, ml, "LE-A", "DK", 2026, require_full_year=False, context=ctx)
>>> res.lines[["line_code", "statement", "amount"]].values.tolist()
[['CASH', 'balance_sheet', 500.0], ['REV', 'income_statement', 500.0]]
>>> res.pbt
500.0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.debit`, `finance.trial_balance.credit`, `finance.trial_balance.closing_balance`, `finance.gl_account.gl_key`, `finance.gl_account.statement`, `finance.gl_account.dk_statutory_map`, `finance.gl_account.de_statutory_map`, `finance.statutory_map_line.map_code`, `finance.statutory_map_line.line_code`, `finance.statutory_map_line.normal_side`, `finance-reporting.statement_line.amount`.

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

# statutory_line_of

```python
statutory_line_of(gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the statutory statement line that each ledger account belongs to, for Denmark and for Germany.

Rule: the map code of the account (dk_statutory_map, de_statutory_map) is looked up in the statutory map lines; the line of an account must belong to the country of its map.

## Args

gl_account: Frame finance.gl_account with gl_key, dk_statutory_map and de_statutory_map, one row per account.
statutory_map_line: Frame finance.statutory_map_line with map_code, country, statement, line_order, line_code, label and normal_side, one row per map code.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with gl_key, country, map_code, statement, line_order, line_code, label and normal_side: one row per account and country.

## Raises

FrameError: a column is missing, a key is duplicated, an account has no map, a map code is not in the map lines, or a map belongs to the other country.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import statutory_line_of
>>> ctx = Context(stage="month12", role="analyst")
>>> accounts = pd.DataFrame({"gl_key": ["GL-1"], "dk_statutory_map": ["DK-A"], "de_statutory_map": ["DE-A"]})
>>> lines = pd.DataFrame({"map_code": ["DK-A", "DE-A"], "country": ["DK", "DE"], "statement": ["IS", "IS"], "line_order": [1, 1], "line_code": ["REV", "REV"],
...                       "label": ["Revenue", "Umsatz"], "normal_side": ["credit", "credit"]})
>>> statutory_line_of(accounts, lines, context=ctx)[["gl_key", "country", "line_code", "label"]].sort_values("country").values.tolist()
[['GL-1', 'DE', 'REV', 'Umsatz'], ['GL-1', 'DK', 'REV', 'Revenue']]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.gl_account.gl_key`, `finance.gl_account.dk_statutory_map`, `finance.gl_account.de_statutory_map`, `finance.statutory_map_line.map_code`, `finance.statutory_map_line.line_code`.

# supplier_spend

```python
supplier_spend(supplier_invoice: pd.DataFrame, supplier: pd.DataFrame, start: dt.date | str, end: dt.date | str, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need what was spent per supplier and category in DKK over a range of invoice dates.

Rule: invoices dated from start to end, both days included; credit notes count negative.

## Args

supplier_invoice: Frame finance.supplier_invoice with sup_key, invoice_type, invoice_date and net_amount_dkk.
supplier: Frame procurement.supplier with sup_key and category, one row per supplier.
start: First day.
end: Last day.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sup_key, category, n_invoices and spend_dkk, sorted by supplier.

## Raises

FrameError: a column is missing, a supplier or an invoice key is duplicated, start is after end, or an invoice is from a supplier that is not in the supplier frame.
PeriodError: start or end is a number, not a date, an unreadable text or has a time zone.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import supplier_spend
>>> ctx = Context(stage="month12", role="analyst")
>>> import datetime as dt
>>> invoices = pd.DataFrame({"sup_key": ["SUP-1"] * 2, "invoice_type": ["invoice", "credit_note"], "invoice_date": ["2026-01-05", "2026-01-20"], "net_amount_dkk": [100.0, 30.0]})
>>> suppliers = pd.DataFrame({"sup_key": ["SUP-1"], "category": ["steel"]})
>>> supplier_spend(invoices, suppliers, dt.date(2026, 1, 1), dt.date(2026, 1, 31), context=ctx).values.tolist()
[['SUP-1', 'steel', 2, 70.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice.sup_key`, `finance.supplier_invoice.invoice_type`, `finance.supplier_invoice.invoice_date`, `finance.supplier_invoice.net_amount_dkk`, `procurement.supplier.sup_key`, `procurement.supplier.category`.

# three_way_match

```python
three_way_match(supplier_invoice_line: pd.DataFrame, goods_receipt: pd.DataFrame, *, price_tolerance_percent: float = 0.0, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you check each supplier invoice line against the purchase order price and the quantity accepted on the receipt.

Rule (quantity first): a credit note is credit_for_rejected_goods; a line without a PO price is non_po; an invoiced quantity above the accepted quantity is quantity_variance; a price difference beyond the tolerance is price_variance; otherwise matched. price_variance is (invoice price less PO price) times quantity, to the cent. The stored status and variance are shown beside the recomputed ones.

## Args

supplier_invoice_line: Frame finance.supplier_invoice_line with sinv_key, line_no, po_key, po_line_no, receipt_no, quantity, unit_price, po_unit_price, invoice_type, match_status and price_variance.
goods_receipt: Frame procurement.goods_receipt with po_key, line_no, receipt_no and qty_accepted.
price_tolerance_percent: Largest accepted price difference in percent, zero or more. Default 0 (PROPOSED; the plan recommends a policy value).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with sinv_key, line_no, po_key, status, price_variance, price_diff_percent, stored_status, stored_price_variance and agrees.

## Raises

FrameError: a column is missing, the tolerance is not a finite number of zero or more, a line or a receipt key is repeated, a PO line has a null price or quantity, or a PO line has no goods receipt.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import three_way_match
>>> ctx = Context(stage="month12", role="analyst")
>>> lines = pd.DataFrame({"sinv_key": ["S1", "S2"], "line_no": [1, 1], "po_key": ["PO-1"] * 2, "po_line_no": [1, 2], "receipt_no": [1, 1], "quantity": [10, 10],
...                       "unit_price": [11.0, 10.0], "po_unit_price": [10.0, 10.0], "invoice_type": ["invoice"] * 2, "match_status": ["matched"] * 2, "price_variance": [10.0, 0.0]})
>>> receipt = pd.DataFrame({"po_key": ["PO-1"] * 2, "line_no": [1, 2], "receipt_no": [1, 1], "qty_accepted": [10, 8]})
>>> three_way_match(lines, receipt, context=ctx)[["sinv_key", "status", "price_variance"]].values.tolist()
[['S1', 'price_variance', 10.0], ['S2', 'quantity_variance', 0.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.supplier_invoice_line.sinv_key`, `finance.supplier_invoice_line.line_no`, `finance.supplier_invoice_line.po_key`, `finance.supplier_invoice_line.po_line_no`, `finance.supplier_invoice_line.receipt_no`, `finance.supplier_invoice_line.quantity`, `finance.supplier_invoice_line.unit_price`, `finance.supplier_invoice_line.po_unit_price`, `finance.supplier_invoice_line.invoice_type`, `finance.supplier_invoice_line.match_status`, `finance.supplier_invoice_line.price_variance`, `procurement.goods_receipt.po_key`, `procurement.goods_receipt.line_no`, `procurement.goods_receipt.receipt_no`, `procurement.goods_receipt.qty_accepted`.

# tie_out

```python
tie_out(ledger_gross: pd.DataFrame, hr_aggregate: pd.DataFrame, *, tolerance: float | None = None, band_floor_factor: float = 0.97, band_ceiling_factor: float = 1.02, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you check the gross pay of the ledger against the aggregate of the hr side, per group of cost centres and month.

Rule: the ledger gross pay of all cost centres of a group of the aggregate is compared with its hr gross pay; they are tied when the difference (ledger less hr) is within tolerance. The ledger must also sit between the band minimum total times band_floor_factor and the band maximum total times band_ceiling_factor. Status is tied, difference, outside_band, suppressed (the aggregate hides the row) or ledger_only (the ledger has a cost centre that no group holds). This is an internal consistency check, not an audit, and no pay per person is accepted.

## Args

ledger_gross: The result of ledger_gross_pay, with le_key, cc_key, period and ledger_gross_pay, one row per entity, cost centre and month.
hr_aggregate: The result of halvaro.hr.payroll_aggregate with le_key, cc_key, period, currency, hr_gross_pay, band_minimum_total, band_maximum_total, cost_centres (comma separated) and suppressed.
tolerance: Largest accepted difference per group and month. None takes the fact policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk (proposed). Optional.
band_floor_factor: Factor on the band minimum total. Default 0.97 (proposed).
band_ceiling_factor: Factor on the band maximum total. Default 1.02 (proposed).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, cc_key, period, cost_centres, currency, ledger_gross_pay, hr_gross_pay, difference, band_minimum_total, band_maximum_total, within_tolerance, within_band_envelope and status.

## Raises

FrameError: a column is missing, a frame has a column that names a person or a base salary, tolerance or a factor is not a valid number, a ledger or aggregate row is repeated, suppressed or cost_centres is null or not valid, an unsuppressed row has a null pay or band total, or a cost centre is in two groups of the same month.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import tie_out
>>> ctx = Context(stage="month12", role="analyst")
>>> ledger = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "ledger_gross_pay": [1000.0]})
>>> hr = pd.DataFrame({"le_key": ["LE-01"], "cc_key": ["CC-1"], "period": ["2026-01"], "currency": ["DKK"], "hr_gross_pay": [1000.0], "band_minimum_total": [900.0],
...                    "band_maximum_total": [1100.0], "cost_centres": ["CC-1"], "suppressed": [False]})
>>> tie_out(ledger, hr, context=ctx).value[["cc_key", "difference", "status"]].values.tolist()
[['CC-1', 0.0, 'tied']]
>>> tie_out(ledger, hr.assign(hr_gross_pay=900.0), context=ctx).value["status"].tolist()
['difference']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `policy.reconciliation.tolerance.payroll_per_cost_centre_month_dkk`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.cc_key`, `finance.payroll_hr_reconciliation.difference`, `finance.payroll_hr_reconciliation.within_tolerance`, `finance.payroll_hr_reconciliation.within_band_envelope`.

# to_natural_sign

```python
to_natural_sign(frame: pd.DataFrame, gl_account: pd.DataFrame, column: str = 'amount', gl_column: str = 'gl_key', *, context: <class 'halvaro.core.access.Context'>) -> pd.Series
```

Use this when a ledger column is debit positive and you need it in the sign people read: revenue and liabilities positive.

Rule: the amount of a line on a credit normal account is multiplied by minus one, a line on a debit normal account is kept. A zero stays zero (never minus zero).

## Args

frame: Frame with the amount column and the account column.
gl_account: Frame finance.gl_account with gl_key and normal_balance (debit or credit), one row per account.
column: Name of the amount column. Default "amount".
gl_column: Name of the account column. Default "gl_key".
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.Series named like the amount column, on the index of the frame.

## Raises

FrameError: a column is missing, gl_account has an account twice or a normal_balance that is neither debit nor credit, or a row names an account that is not in gl_account.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import to_natural_sign
>>> ctx = Context(stage="month12", role="analyst")
>>> accounts = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "normal_balance": ["debit", "credit"]})
>>> lines = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "amount": [100.0, -40.0]})
>>> to_natural_sign(lines, accounts, context=ctx).tolist()
[100.0, 40.0]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.gl_account.gl_key`, `finance.gl_account.normal_balance`.

# translation_check

```python
translation_check(trial_balance: pd.DataFrame, *, month: int = 12, rate_tolerance: float = 0.001, eur_rate: float | None = None, context: <class 'halvaro.core.access.Context'>) -> Envelope
```

Use this when you check the rounding of the line by line EUR to DKK translation of a trial balance at each fiscal year end.

Rule: per period of the chosen month, the stored DKK closing balance of the EUR lines is compared with the closing balance times the fixed rate rounded to the cent (half away from zero). At a fixed rate only cent rounding is left, so the difference is the stored sum less the recomputed sum. A period whose EUR lines (balance above 1 in absolute value) are translated at an implied rate (sum of DKK over sum of EUR, absolute values) that differs from the fixed rate by more than rate_tolerance is an error, because a translation difference would arise.

## Args

trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-12), gl_key, closing_balance, currency and closing_balance_dkk.
month: The month number (1 to 12) that ends the fiscal year. Default 12 (proposed).
rate_tolerance: Largest accepted gap between the implied rate and the fixed rate. Default 0.001 (proposed).
eur_rate: The EUR to DKK rate to test against; None takes the fixed rate of the core fact world.fx_eur_dkk_fixed. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with period, n_lines, sum_dkk, sum_recomputed_dkk, rounding_dkk (stored less recomputed) and max_line_rounding_dkk, one row per period of the month; empty when no EUR line is in that month.

## Raises

FrameError: a column is missing, month is not a whole number from 1 to 12, eur_rate is not a positive number, or the EUR lines of a period are translated at a rate that differs from the fixed rate by more than rate_tolerance.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import translation_check
>>> ctx = Context(stage="month12", role="analyst")
>>> tb = pd.DataFrame({"le_key": ["LE-02"], "period": ["2026-12"], "gl_key": ["GL-1"], "closing_balance": [100.0], "currency": ["EUR"], "closing_balance_dkk": [750.01]})
>>> translation_check(tb, eur_rate=7.5, context=ctx).value[["period", "n_lines", "rounding_dkk"]].values.tolist()
[['2026-12', 1, 0.01]]
>>> translation_check(tb, month=13, eur_rate=7.5, context=ctx)
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: month is a whole month number from 1 to 12
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `finance.trial_balance.le_key`, `finance.trial_balance.period`, `finance.trial_balance.gl_key`, `finance.trial_balance.closing_balance`, `finance.trial_balance.currency`, `finance.trial_balance.closing_balance_dkk`.

# utilisation

```python
utilisation(mgmt_pl_department: pd.DataFrame, *, by: str = 'period', tolerance: float = 0.01, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need booked hours over available hours in percent, per department and period or per department over all periods.

Rule: utilisation is (project hours plus service hours) over available hours times 100. by="period" gives each row of the entity, department and period with the recomputed value, the stored utilisation_pct and whether they agree within tolerance (PROPOSED 0.01); rows without available hours have a null utilisation. by="department" adds the hours of all periods per entity and department first, so the result is a ratio of sums and not a mean of percents.

## Args

mgmt_pl_department: Frame finance.mgmt_pl_department with le_key, dep_key, period, utilisation_pct, project_hours, service_hours and available_hours, one row per entity, department and period.
by: "period" or "department" (default "period").
tolerance: Largest accepted difference between the recomputed and the stored utilisation_pct, in percentage points (default 0.01, PROPOSED).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame. With by="period": le_key, dep_key, period, project_hours, service_hours, available_hours, utilisation_pct, stored_utilisation_pct and agrees. With by="department": le_key, dep_key, the three hour columns summed and utilisation_pct to two decimals.

## Raises

FrameError: a column is missing, by is not "period" or "department", tolerance is negative or not a number, a row is repeated for an entity, department and period, or an hour value is negative.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import utilisation
>>> ctx = Context(stage="month3", role="analyst")
>>> hours = pd.DataFrame({"le_key": ["LE-01"] * 2, "dep_key": ["DEP-1"] * 2, "period": ["2026-01", "2026-02"], "utilisation_pct": [75.0, 80.0],
...                      "project_hours": [100.0, 120.0], "service_hours": [20.0, 20.0], "available_hours": [160.0, 175.0]})
>>> utilisation(hours, context=ctx)[["period", "utilisation_pct", "agrees"]].to_dict("records")
[{'period': '2026-01', 'utilisation_pct': 75.0, 'agrees': True}, {'period': '2026-02', 'utilisation_pct': 80.0, 'agrees': True}]
>>> utilisation(hours, by="department", context=ctx)["utilisation_pct"].tolist()
[77.61]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.mgmt_pl_department.le_key`, `finance.mgmt_pl_department.dep_key`, `finance.mgmt_pl_department.period`, `finance.mgmt_pl_department.utilisation_pct`, `finance.mgmt_pl_department.project_hours`, `finance.mgmt_pl_department.service_hours`, `finance.mgmt_pl_department.available_hours`.

# write_down_journal

```python
write_down_journal(manual: pd.DataFrame, prj_key: str, *, gl_key: str = 'GL-5190', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the write-down lines booked on one project, from the manual journals.

Rule: the rows of the manual journals on the project and on the write-down account, in the order of posting date and journal number. There is no guess from a change of margin: a project without such a row gives an empty frame.

## Args

manual: The manual journals, the output of ledger.manual_journals, with le_key, journal_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk.
prj_key: The project key.
gl_key: The write-down account. PROPOSED default GL-5190, until the fact fin.project_accounting.write_down_gl_key exists.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, journal_no, posting_date, description, currency, amount and amount_dkk; empty when the project has no write-down.

## Raises

FrameError: a column is missing or a posting date is not a date.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import write_down_journal
>>> ctx = Context(stage="month3", role="analyst")
>>> manual = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": ["J-2", "J-1"], "posting_date": ["2026-03-31", "2026-02-28"], "description": ["write down"] * 2,
...                        "gl_key": ["GL-5190"] * 2, "prj_key": ["PRJ-2"] * 2, "currency": ["DKK"] * 2, "amount": [50.0, 25.0], "amount_dkk": [50.0, 25.0]})
>>> write_down_journal(manual, "PRJ-2", context=ctx)[["journal_no", "posting_date", "amount_dkk"]].to_dict("records")
[{'journal_no': 'J-1', 'posting_date': '2026-02-28', 'amount_dkk': 25.0}, {'journal_no': 'J-2', 'posting_date': '2026-03-31', 'amount_dkk': 50.0}]
>>> write_down_journal(manual, "PRJ-9", context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_header.source`, `finance.journal_header.posting_date`, `finance.journal_line.prj_key`, `finance.journal_line.gl_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`.
