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
