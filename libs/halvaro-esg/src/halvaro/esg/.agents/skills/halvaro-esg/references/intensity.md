# intensity

Module `halvaro.esg.ghg`. Import: `from halvaro.esg import intensity`.

```python
intensity(L: pd.DataFrame, SR: pd.DataFrame, year: int | None = None, basis: str = 'current', *, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the emissions in tonnes CO2e per employee and per DKK million of revenue, per legal entity and for the company.

Tonnes CO2e per employee and per DKK million of revenue, per legal entity and for the company ('ALL', from the consolidated group row of the statutory report: its revenue is already in DKK without
the intercompany sales). Emissions are the scope totals of the year on `basis`; location based and market based totals are both given, never added. Revenue of an EUR entity is converted at the
fixed rate world.fx_eur_dkk_fixed. A year without a statutory report row gives null denominators. Property: all ratios are above zero for a year with lines.

Args:
    L: Frame energy-esg.emission_line with le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period (supersedes_line_no when lines are restated).
    SR: Frame finance-reporting.statutory_report with le_key, scope ('entity' or 'group'), fiscal_year, revenue, average_employees and currency.
    year: The whole year, like 2025; the year before the year of world.now when None.
    basis: 'current' (superseded originals left out) or 'first_booked' (restated lines left out).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance (status VERIFY+synthetic) whose value is a DataFrame with le_key, year, months (months of lines; under 12 flags a part year), employees, revenue_dkk_m, total_location_t, total_market_t, t_per_employee_location, t_per_employee_market, t_per_dkk_m_location and t_per_dkk_m_market (three decimals), one row per entity and the 'ALL' row last.

Raises:
    FrameError: SR lacks a column, there are no emission lines for the year, the statutory report has more than one row for an entity (or the group) and the year, a revenue currency is not DKK or EUR, or the emission lines fail as in scope_totals (missing column, null kgco2e, bad year, basis or scope, restated lines not flagged).
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import intensity
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
    >>> L = pd.DataFrame([
    ...     ("LE-900001", "2025-01", 1, "stationary_combustion", 1, None, None, 100000.0, False, None),
    ...     ("LE-900001", "2025-02", 3, "purchased_goods", 1, None, "3.1", 50000.0, False, None)], columns=cols)
    >>> SR = pd.DataFrame({"le_key": ["LE-900001", "GROUP-900001"], "scope": ["entity", "group"], "fiscal_year": [2025, 2025],
    ...                    "revenue": [50000000.0, 50000000.0], "average_employees": [100, 100], "currency": ["DKK", "DKK"]})
    >>> r = intensity(L, SR, 2025, context=ctx)
    >>> r.value[["le_key", "employees", "revenue_dkk_m", "total_location_t", "t_per_employee_location", "t_per_dkk_m_location"]].values.tolist()
    [['LE-900001', 100.0, 50.0, 150.0, 1.5, 3.0], ['ALL', 100.0, 50.0, 150.0, 1.5, 3.0]]

## Source columns

- `energy-esg.emission_line.le_key`
- `energy-esg.emission_line.period`
- `energy-esg.emission_line.scope`
- `energy-esg.emission_line.category`
- `energy-esg.emission_line.line_no`
- `energy-esg.emission_line.method`
- `energy-esg.emission_line.ghg_category`
- `energy-esg.emission_line.kgco2e`
- `energy-esg.emission_line.is_superseded`
- `energy-esg.emission_line.restated_from_period`
- `finance-reporting.statutory_report.le_key`
- `finance-reporting.statutory_report.fiscal_year`
- `finance-reporting.statutory_report.revenue`
- `finance-reporting.statutory_report.average_employees`
- `finance-reporting.statutory_report.currency`
- `finance-reporting.statutory_report.scope`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `world.now`
- `world.fx_eur_dkk_fixed`
