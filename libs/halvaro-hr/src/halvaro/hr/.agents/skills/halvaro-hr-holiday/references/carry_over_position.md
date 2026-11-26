# carry_over_position

```python
carry_over_position(ent: pd.DataFrame) -> CarryOverRows
```

Use this when you need to compare the days carried into each holiday year with the cap that applies to the person, and see the headroom that is left.

Rule: basis is "agreement" for a DK row whose carry_over_agreement flag is set, otherwise "default" (DE rows have the default only). cap is the cap fact of that basis. headroom = cap -
carried_in_days, so a carry-in above its cap shows as negative headroom. at_cap is True when headroom is zero. An opening row (opening_balance True) is the start value of the data window:
it has no cap and no headroom, and at_cap is False. For DE rows deadline is the date given by the deadline facts in the year of the label; DK rows have no deadline.

## Args

ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement, opening_balance.

## Returns

CarryOverRows: an immutable sequence of CarryOverRow, one per entitlement row. Fields of a row: emp_key, holiday_year, carried_in_days (days), carry_over_agreement (flag),
opening_balance (flag), country (DK or DE), basis ("default" or "agreement"), cap (days, None on an opening row), headroom (days, None on an opening row), at_cap (flag),
deadline (date, DE only, else None), legal_status (status of the facts). Every field carries a description and a unit (CarryOverRow.columns()). result.to_frame() gives the DataFrame.

## Raises

FrameError: the frame lacks a required column, or a holiday year label matches no label format.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import fact
>>> from halvaro.hr import carry_over_position
>>> cap = fact("legal.DK.holiday.carryover.default_max_days").value
>>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "holiday_year": ["2026/27", "2026/27"], "carried_in_days": [cap, cap + 1],
...                     "carry_over_agreement": [False, False], "opening_balance": [False, False]})
>>> position = carry_over_position(ent)
>>> [row.headroom for row in position], [row.at_cap for row in position]
([0.0, -1.0], [True, False])
```

## Typed result

`CarryOverRows`, a sequence of `CarryOverRow`; `to_frame()` gives the DataFrame. Fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.DK.holiday.carryover.default_max_days`, `legal.DE.holiday.carryover.default_max_days`, `legal.DK.holiday.carryover.agreement_max_days`, `legal.DK.holiday.label_format`, `legal.DE.holiday.label_format`, `legal.DE.holiday.carryover.deadline_month_day.month`, `legal.DE.holiday.carryover.deadline_month_day.day`.

Source columns: `hr.holiday_entitlement.emp_key`, `hr.holiday_entitlement.holiday_year`, `hr.holiday_entitlement.carried_in_days`, `hr.holiday_entitlement.carry_over_agreement`, `hr.holiday_entitlement.opening_balance`.
