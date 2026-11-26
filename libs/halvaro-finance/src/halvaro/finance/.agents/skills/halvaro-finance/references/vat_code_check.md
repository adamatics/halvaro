# vat_code_check

```python
vat_code_check(journal_line: pd.DataFrame, *, min_base: float = 1000.0, ratio_tolerance: float = 0.001, tolerance: float = 0.005, settlement_sources: tuple[str, ...] = ('treasury', 'opening'), vat_accounts: tuple[str, ...] = ('GL-2510', 'GL-2520', 'GL-2530', 'GL-4710', 'GL-4720', 'GL-4740'), context: Context) -> Envelope
```

Use this when you need to check that the VAT codes of the ledger lines carry the right rate, sit on the right accounts and agree with the postings on the VAT accounts.

Rule: a domestic code (DK25, DE19) carries the standard rate of its country on its base: |vat amount / vat_base - rate| must be within ratio_tolerance for lines with a base of at least min_base
(rule rate_mismatch). The rate is the fact fin.vat.<country>.standard_rate (status VERIFY). A code on a line outside the VAT accounts and the revenue and cost accounts is code_on_wrong_account.
A code that belongs to no box is code_in_no_box, a domestic code of the other country is code_of_other_country, a domestic code on a VAT account without a base is missing_vat_base. Per
entity and month the postings of documents on the VAT accounts must equal the coded lines within `tolerance` (vat_account_differs_from_coded_lines); sources in settlement_sources are left
out because the return journals that clear the accounts carry no code.

## Args

journal_line: Frame finance.journal_line with le_key, gl_key, period, amount, vat_code, vat_base and source.
min_base: Smallest vat_base that is rate checked, in currency units (default 1000.0, PROPOSED).
ratio_tolerance: Largest accepted difference between the observed and the standard rate, a share (default 0.001, PROPOSED).
tolerance: Largest accepted difference of postings and coded lines, in currency units (default 0.005).
settlement_sources: Journal sources of the return journals that are left out of the account check (default treasury and opening).
vat_accounts: The VAT accounts (default the output and input accounts of the box layout).
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

Envelope whose value is a DataFrame of violations with the columns table (finance.journal_line), key, rule and detail (what was observed), empty when the coding is clean. The key is
text of words separated by one space: `<le_key> <period> <gl_key>` for the rules on a line (rate_mismatch, code_in_no_box, code_on_wrong_account, code_of_other_country,
missing_vat_base) and `<le_key> <period>` for vat_account_differs_from_coded_lines, so the period of a violation is the second word of its key. The envelope carries the VERIFY status of
the rate facts. Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

## Raises

FrameError: a column is missing, a tolerance is negative or not a number, or a period is not text like 2025-02.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import vat_code_check
>>> ctx = Context(stage="month3", role="analyst")
>>> cols = ["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "source"]
>>> clean = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "ar")], columns=cols)
>>> vat_code_check(clean, context=ctx).value.empty
True
>>> off = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -240.0, "DK25", 1000.0, "ar")], columns=cols)
>>> vat_code_check(off, context=ctx).value["rule"].tolist()
['rate_mismatch']
>>> vat_code_check(off, context=ctx).value["key"].tolist()
['LE-01 2025-01 GL-4710']
```

## Typed result

`ViolationRow`, fields and units on the page `results.md`.

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `fin.vat.DK.standard_rate`, `fin.vat.DE.standard_rate`.

Source columns: `finance.journal_line.le_key`, `finance.journal_line.gl_key`, `finance.journal_line.period`, `finance.journal_line.amount`, `finance.journal_line.vat_code`, `finance.journal_line.vat_base`, `finance.journal_line.source`.
