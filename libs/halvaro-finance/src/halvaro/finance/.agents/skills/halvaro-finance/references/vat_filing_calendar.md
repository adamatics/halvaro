# vat_filing_calendar

```python
vat_filing_calendar(vat_return: pd.DataFrame, *, context: Context) -> Envelope
```

Use this when you need the filing due date of each VAT return and want to compare it with the stored date.

Rule: the due date is the day of the month given by the fact frep.vat.<country>.filing_due_day_of_next_month (status VERIFY) in the month after the period, moved to the next working day of the
filing office. The office is the holiday region of the entity (LE-01 Denmark, LE-02 Hamburg; PROPOSED).

## Args

vat_return: Frame finance-reporting.vat_return with le_key, period (text like 2025-02) and filing_due_date.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, period, due_date, stored_due_date (both dates) and agrees (yes or no). The envelope carries the VERIFY status of the day facts.
Typed form: FilingDateRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing or an entity has no country.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import vat_filing_calendar
>>> ctx = Context(stage="month12", role="analyst")
>>> ret = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "filing_due_date": [None]})
>>> r = vat_filing_calendar(ret, context=ctx).value
>>> (r.loc[0, "due_date"].year, r.loc[0, "due_date"].month, bool(r.loc[0, "agrees"]))
(2025, 2, False)
```

## Typed result

`FilingDateRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `frep.vat.DK.filing_due_day_of_next_month`, `frep.vat.DE.filing_due_day_of_next_month`.

Source columns: `finance-reporting.vat_return.le_key`, `finance-reporting.vat_return.period`, `finance-reporting.vat_return.filing_due_date`.
