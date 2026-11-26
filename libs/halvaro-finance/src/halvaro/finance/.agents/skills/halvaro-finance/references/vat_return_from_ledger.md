# vat_return_from_ledger

```python
vat_return_from_ledger(journal_line: pd.DataFrame, *, boxes: dict[str, Any] = {'output_domestic': (('GL-4710', 'GL-4720'), ('DK25', 'DE19')), 'output_acquisition_eu': (('GL-4710', 'GL-4720'), ('RC-EU',)), 'output_acquisition_non_eu': (('GL-4710', 'GL-4720'), ('RC-NONEU',)), 'input_domestic': (('GL-2510', 'GL-2520'), ('DK25', 'DE19')), 'input_acquisition_eu': (('GL-2510', 'GL-2520'), ('RC-EU',)), 'input_acquisition_non_eu': (('GL-2510', 'GL-2520'), ('RC-NONEU',)), 'input_import': (('GL-2510', 'GL-2520'), ())}, context: Context) -> Envelope
```

Use this when you need the VAT return of each entity and month rebuilt from the VAT coded ledger lines.

Rule: output boxes read the credit side of the output accounts (GL-4710, GL-4720) and input boxes the debit side of the input accounts (GL-2510, GL-2520), each box by its VAT codes. The taxable base
of a box is the sum of vat_base of its lines. vat_payable = total_output_vat less total_input_vat. Every month from the first to the last period of the entity is listed, a month without lines
has zeros. The box layout is a generator placeholder (fact frep.vat.boxes, status VERIFY) and its status is carried in the envelope.

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, period (text like 2025-02), amount (debit positive), vat_code, vat_base and currency.
boxes: Optional box layout: box name to (accounts, VAT codes). The default is the placeholder layout; the names of the boxes must stay the default names.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame with le_key, period, currency, output_vat_domestic, output_vat_acquisition_eu, output_vat_acquisition_non_eu, input_vat_domestic, input_vat_acquisition_eu, input_vat_acquisition_non_eu,
input_vat_import, total_output_vat, total_input_vat, vat_payable (all in the currency of the entity), taxable_base_domestic_sales, taxable_base_acquisitions_eu,
taxable_base_acquisitions_non_eu and taxable_base_domestic_purchases. The envelope carries the status of the box facts (VERIFY).
Typed form: VatReturnRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, a period is not text like 2025-02, an entity has lines in more than one currency, or the box names differ from the default names.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import vat_return_from_ledger
>>> ctx = Context(stage="month3", role="analyst")
>>> lines = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "DKK"), ("LE-01", "GL-2510", "2025-01", 100.0, "DK25", 400.0, "DKK")],
...                      columns=["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency"])
>>> env = vat_return_from_ledger(lines, context=ctx)
>>> env.value.loc[0, ["total_output_vat", "total_input_vat", "vat_payable"]].tolist() == [250.0, 100.0, 150.0]
True
>>> env.status
'VERIFY'
```

## Typed result

`VatReturnRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `frep.vat.boxes.output_domestic.label`, `frep.vat.boxes.output_acquisition_eu.label`, `frep.vat.boxes.output_acquisition_non_eu.label`, `frep.vat.boxes.input_domestic.label`, `frep.vat.boxes.input_acquisition_eu.label`, `frep.vat.boxes.input_acquisition_non_eu.label`, `frep.vat.boxes.input_import.label`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`, `finance.journal_line.vat_code`, `finance.journal_line.vat_base`, `finance.journal_line.currency`.
