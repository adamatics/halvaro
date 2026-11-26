# size_evidence

Module `halvaro.esg.basis`. Import: `from halvaro.esg import size_evidence`.

```python
size_evidence(SR: pd.DataFrame, *, country_of: Mapping[str, Any] = {'LE-01': 'DK', 'LE-02': 'DE'}, context: halvaro.core.access.Context) -> Provenance
```

Use this when you need the employees and revenue of each legal entity and year set against the provisional size thresholds of its country, as evidence only.

Employees and revenue of each legal entity and year against the provisional size thresholds of its country (core facts, VERIFY; the revenue is in the currency of the entity). A null employee count or revenue gives a null (unknown) comparison, never false. The balance sheet criterion is not evaluated here (employees and revenue only, as the plan lists). Evidence only: no column says that a duty applies. Group rows (scope other than entity) are left out. The thresholds are read from the core facts, which are listed in the facts used of the result.

Args:
    SR: The finance-reporting.statutory_report table with the columns le_key, fiscal_year, average_employees, revenue and reporting_class, and scope when group rows are present.
    country_of: Mapping from le_key to the country code of the legal entity (PROPOSED: the default maps the two legal entities of hr.legal_entity.country); only DK and DE have thresholds.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    Provenance whose value is a DataFrame with the columns le_key, fiscal_year, country, average_employees, threshold_employees, exceeds_employees, revenue, threshold_revenue, exceeds_revenue and reporting_class (as stored), sorted by le_key and fiscal_year; the facts used are the thresholds, and a warning says that the evidence is provisional.

Raises:
    FrameError: SR lacks le_key, fiscal_year, average_employees, revenue or reporting_class.
    FrameError: SR has no entity rows, an entity row has no le_key, or an entity and year has more than one row.
    FrameError: an entity has no country in `country_of`.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import size_evidence
    >>> ctx = Context(stage="month12", role="analyst")
    >>> SR = pd.DataFrame({"le_key": ["LE-900001", "LE-900001"], "fiscal_year": [2024, 2025], "average_employees": [5.0, None],
    ...                    "revenue": [1000.0, 2000.0], "reporting_class": ["small", "small"], "scope": ["entity", "entity"]})
    >>> r = size_evidence(SR, country_of={"LE-900001": "DK"}, context=ctx)
    >>> r.value["country"].tolist()
    ['DK', 'DK']
    >>> r.value["exceeds_revenue"].tolist()
    [False, False]
    >>> bool(r.value["exceeds_employees"].isna().tolist()[1])
    True

## Source columns

- `finance-reporting.statutory_report.le_key`
- `finance-reporting.statutory_report.fiscal_year`
- `finance-reporting.statutory_report.average_employees`
- `finance-reporting.statutory_report.revenue`
- `finance-reporting.statutory_report.reporting_class`
- `finance-reporting.statutory_report.scope`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `frep.annual_reports.DK.size_thresholds.net_revenue`
- `frep.annual_reports.DE.size_thresholds.net_revenue`
- `frep.annual_reports.DK.size_thresholds.average_full_time_employees`
- `frep.annual_reports.DE.size_thresholds.average_employees`
