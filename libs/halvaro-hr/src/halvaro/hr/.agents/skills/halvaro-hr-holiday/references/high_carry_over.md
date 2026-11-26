# high_carry_over

```python
high_carry_over(ent: pd.DataFrame, holiday_year: str = '2026/27', country: str = 'DK', threshold: float | PolicyDefault = policy:policy.holiday.high_carry_over_days) -> HighCarryOverRows
```

Use this when you need the people who carry more holiday days into a holiday year than a threshold, so that a person can look at each of them.

Rule: rows of the holiday year whose carried_in_days is strictly above the threshold, opening rows left out. The default threshold is the fact policy.holiday.high_carry_over_days (status
proposed). When the default is used the result carries policy_status with the status of that fact (by fact id); a number given by the caller is used as it is and policy_status is empty. The flag is a hint for a look at one
person, not a limit, and it is meant for the country given (default DK).

## Args

ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement, opening_balance.
holiday_year: Holiday year label to look at.
country: "DK" or "DE". The label must be a label of this country.
threshold: Days. Carried-in days above this value are listed. Default: the policy fact.

## Returns

HighCarryOverRows: an immutable sequence of HighCarryOverRow sorted by emp_key. Fields of a row: emp_key, holiday_year, carried_in_days (days), carry_over_agreement (flag),
legal_status (status of the facts). Every field carries a description and a unit (HighCarryOverRow.columns()). result.to_frame() gives the DataFrame; result.policy_status is the
status of the policy fact behind a default threshold.

## Raises

FrameError: the frame lacks a required column, or holiday_year is not a label of the given country.

## Example

```python
>>> import pandas as pd
>>> from halvaro.hr import high_carry_over
>>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "holiday_year": ["2026/27", "2026/27"], "carried_in_days": [9.0, 2.0],
...                     "carry_over_agreement": [True, False], "opening_balance": [False, False]})
>>> [row.emp_key for row in high_carry_over(ent, threshold=3.0)]
['EMP-1']
>>> from halvaro.core import fact
>>> dict(high_carry_over(ent).policy_status) == {'policy.holiday.high_carry_over_days': fact('policy.holiday.high_carry_over_days').status}
True
```

## Typed result

`HighCarryOverRows`, a sequence of `HighCarryOverRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`, `policy.holiday.high_carry_over_days`.

Source columns: `hr.holiday_entitlement.emp_key`, `hr.holiday_entitlement.holiday_year`, `hr.holiday_entitlement.carried_in_days`, `hr.holiday_entitlement.carry_over_agreement`, `hr.holiday_entitlement.opening_balance`.
