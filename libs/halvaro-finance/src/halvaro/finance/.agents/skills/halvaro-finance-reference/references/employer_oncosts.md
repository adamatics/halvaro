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
